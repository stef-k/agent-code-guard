"""Tree-sitter feasibility prototype for callable-scoped measurements.

This module is deliberately outside the shipped Code Guard runner. It extracts
one normalized callable model per source file so all three candidate metrics
consume the same parse tree.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from tree_sitter import Node
from tree_sitter_language_pack import get_parser


LANGUAGE_BY_SUFFIX = {".py": "python", ".go": "go", ".kt": "kotlin", ".cs": "csharp"}

CALLABLE_TYPES = {
    "python": {"function_definition"},
    "go": {"function_declaration", "method_declaration"},
    "kotlin": {"function_declaration", "secondary_constructor"},
    "csharp": {"method_declaration", "constructor_declaration", "local_function_statement"},
}

LAMBDA_TYPES = {
    "python": {"lambda"},
    "go": {"func_literal"},
    "kotlin": {"lambda_literal", "anonymous_function"},
    "csharp": {"lambda_expression", "anonymous_method_expression"},
}

CONTROL_TYPES = {
    "python": {"if_statement", "for_statement", "while_statement", "match_statement", "try_statement", "with_statement"},
    "go": {"if_statement", "for_statement", "expression_switch_statement", "type_switch_statement", "select_statement"},
    "kotlin": {"if_expression", "for_statement", "while_statement", "do_while_statement", "when_expression", "try_expression"},
    "csharp": {"if_statement", "for_statement", "foreach_statement", "while_statement", "do_statement", "switch_statement", "try_statement", "using_statement", "lock_statement"},
}

DECISION_TYPES = {
    "python": {"if_statement", "elif_clause", "for_statement", "while_statement", "except_clause", "conditional_expression", "list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression", "case_clause"},
    "go": {"if_statement", "for_statement", "expression_case", "type_case", "communication_case"},
    "kotlin": {"if_expression", "for_statement", "while_statement", "do_while_statement", "catch_block", "when_entry"},
    "csharp": {"if_statement", "for_statement", "foreach_statement", "while_statement", "do_statement", "catch_clause", "conditional_expression", "switch_expression_arm"},
}


@dataclass(frozen=True)
class SourceRange:
    start_line: int
    end_line: int


@dataclass(frozen=True)
class CallableMeasurement:
    language: str
    identity: str
    range: SourceRange
    physical_loc: int
    nesting_depth: int
    cyclomatic_complexity: int

    def to_json(self) -> dict[str, object]:
        value = asdict(self)
        value["range"] = {"startLine": self.range.start_line, "endLine": self.range.end_line}
        value["physicalLoc"] = value.pop("physical_loc")
        value["nestingDepth"] = value.pop("nesting_depth")
        value["cyclomaticComplexity"] = value.pop("cyclomatic_complexity")
        return value


def analyze_file(path: Path) -> list[CallableMeasurement]:
    language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
    if language is None:
        raise ValueError(f"unsupported prototype language: {path.suffix}")
    source = path.read_bytes()
    tree = get_parser(language).parse(source)
    if tree.root_node.has_error:
        raise ValueError(f"unable to parse {path}: syntax tree contains errors")
    return [_measure(node, language, source, path) for node in _callable_nodes(tree.root_node, language)]


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _callable_nodes(root: Node, language: str) -> list[Node]:
    return [node for node in _walk(root) if node.type in CALLABLE_TYPES[language]]


def _measure(node: Node, language: str, source: bytes, path: Path) -> CallableMeasurement:
    start_node = _range_start_node(node, language)
    start_line = start_node.start_point.row + 1
    end_line = node.end_point.row + 1
    return CallableMeasurement(
        language=language,
        identity=_identity(node, language, source, path),
        range=SourceRange(start_line, end_line),
        physical_loc=end_line - start_line + 1,
        nesting_depth=_nesting(node, language),
        cyclomatic_complexity=1 + _decision_count(node, language, source),
    )


def _range_start_node(node: Node, language: str) -> Node:
    if language == "python" and node.parent and node.parent.type == "decorated_definition":
        return node.parent
    return node


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _name(node: Node, language: str, source: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return _text(name, source)
    if language == "kotlin":
        for child in node.named_children:
            if child.type == "simple_identifier":
                return _text(child, source)
    if language in {"kotlin", "csharp"} and "constructor" in node.type:
        owner = _nearest_named_owner(node, language, source)
        return owner or "<constructor>"
    return "<anonymous>"


def _nearest_named_owner(node: Node, language: str, source: bytes) -> str | None:
    owner_types = {
        "python": {"class_definition"},
        "go": {"type_declaration", "type_spec"},
        "kotlin": {"class_declaration", "object_declaration"},
        "csharp": {"class_declaration", "struct_declaration", "record_declaration", "namespace_declaration", "file_scoped_namespace_declaration"},
    }[language]
    current = node.parent
    while current:
        if current.type in owner_types:
            name = current.child_by_field_name("name")
            if name is None and language == "kotlin":
                name = next((child for child in current.named_children if child.type in {"simple_identifier", "type_identifier"}), None)
            if name:
                return _text(name, source)
        current = current.parent
    return None


def _identity(node: Node, language: str, source: bytes, path: Path) -> str:
    parts = [_name(node, language, source)]
    current = node.parent
    owner_types = {
        "python": {"class_definition", "function_definition"},
        "go": set(),
        "kotlin": {"class_declaration", "object_declaration", "function_declaration"},
        "csharp": {"namespace_declaration", "file_scoped_namespace_declaration", "class_declaration", "struct_declaration", "record_declaration", "local_function_statement"},
    }[language]
    while current:
        if current.type in owner_types:
            name = current.child_by_field_name("name")
            if name is None and language == "kotlin":
                name = next((child for child in current.named_children if child.type in {"simple_identifier", "type_identifier"}), None)
            if name:
                parts.append(_text(name, source))
        current = current.parent
    if language == "go":
        receiver = node.child_by_field_name("receiver")
        if receiver:
            receiver_text = _text(receiver, source).replace("(", "").replace(")", "").replace("*", "")
            receiver_type = receiver_text.split()[-1] if receiver_text.split() else "receiver"
            parts.append(receiver_type)
    parts.append(path.stem if language == "python" else _package_or_namespace(node, language, source))
    return ".".join(reversed([part for part in parts if part]))


def _package_or_namespace(node: Node, language: str, source: bytes) -> str:
    root = node
    while root.parent:
        root = root.parent
    candidates = {
        "go": {"package_clause"},
        "kotlin": {"package_header"},
        "csharp": {"file_scoped_namespace_declaration"},
    }.get(language, set())
    for child in root.named_children:
        if child.type in candidates:
            text = _text(child, source).replace("package", "", 1).replace("namespace", "", 1)
            return text.strip().rstrip(";")
    return ""


def _nesting(callable_node: Node, language: str) -> int:
    def visit(node: Node, depth: int) -> int:
        maximum = depth
        for child in node.named_children:
            if (child.type in CALLABLE_TYPES[language] and child is not callable_node) or child.type in LAMBDA_TYPES[language]:
                continue
            increment = 1 if child.type in CONTROL_TYPES[language] else 0
            if child.type in {"elif_clause"}:
                increment = 0
            maximum = max(maximum, visit(child, depth + increment))
        return maximum
    return visit(callable_node, 0)


def _decision_count(callable_node: Node, language: str, source: bytes) -> int:
    count = 0
    for node in _walk_without_nested_callables(callable_node, language):
        if node is callable_node:
            continue
        if node.type in DECISION_TYPES[language] and not _is_default_branch(node, source):
            count += 1
        if node.type in {"boolean_operator", "conjunction_expression", "disjunction_expression", "binary_expression"}:
            count += _short_circuit_operator_count(node, source)
        if language == "csharp" and node.type == "switch_section":
            count += sum(1 for child in node.named_children if child.type == "case_switch_label")
    return count


def _walk_without_nested_callables(root: Node, language: str) -> Iterator[Node]:
    yield root
    for child in root.named_children:
        if child.type in CALLABLE_TYPES[language] or child.type in LAMBDA_TYPES[language]:
            continue
        yield from _walk_without_nested_callables(child, language)


def _is_default_branch(node: Node, source: bytes) -> bool:
    text = _text(node, source).lstrip()
    return text.startswith(("default", "else", "case _", "_ ->", "_ =>"))


def _short_circuit_operator_count(node: Node, source: bytes) -> int:
    direct_tokens = [_text(child, source) for child in node.children if not child.is_named]
    return sum(token in {"and", "or", "&&", "||"} for token in direct_tokens)
