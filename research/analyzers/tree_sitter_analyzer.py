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

from research.analyzers.source_regions import ExecutableRegion, executable_regions

CALLABLE_TYPES = {
    "python": {"function_definition"},
    "go": {"function_declaration", "method_declaration"},
    "kotlin": {"function_declaration", "secondary_constructor"},
    "csharp": {"method_declaration", "constructor_declaration", "local_function_statement"},
    "java": {"method_declaration", "constructor_declaration"},
    "javascript": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
    "typescript": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
    "tsx": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
}

LAMBDA_TYPES = {
    "python": {"lambda"},
    "go": {"func_literal"},
    "kotlin": {"lambda_literal", "anonymous_function"},
    "csharp": {"lambda_expression", "anonymous_method_expression"},
    "java": {"lambda_expression"},
    "javascript": set(),
    "typescript": set(),
    "tsx": set(),
}

CONTROL_TYPES = {
    "python": {"if_statement", "for_statement", "while_statement", "match_statement", "try_statement"},
    "go": {"if_statement", "for_statement", "expression_switch_statement", "type_switch_statement", "select_statement"},
    "kotlin": {"if_expression", "for_statement", "while_statement", "do_while_statement", "when_expression", "try_expression"},
    "csharp": {"if_statement", "for_statement", "foreach_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "java": {"if_statement", "for_statement", "enhanced_for_statement", "while_statement", "do_statement", "switch_expression", "try_statement"},
    "javascript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "typescript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "tsx": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
}

DECISION_TYPES = {
    "python": {"if_statement", "elif_clause", "for_statement", "while_statement", "except_clause", "conditional_expression", "list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression", "case_clause"},
    "go": {"if_statement", "for_statement", "expression_case", "type_case", "communication_case"},
    "kotlin": {"if_expression", "for_statement", "while_statement", "do_while_statement", "catch_block", "when_entry"},
    "csharp": {"if_statement", "for_statement", "foreach_statement", "while_statement", "do_statement", "catch_clause", "conditional_expression", "switch_expression_arm"},
    "java": {"if_statement", "for_statement", "enhanced_for_statement", "while_statement", "do_statement", "catch_clause", "ternary_expression"},
    "javascript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "catch_clause", "ternary_expression"},
    "typescript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "catch_clause", "ternary_expression"},
    "tsx": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "catch_clause", "ternary_expression"},
}


@dataclass(frozen=True)
class SourceRange:
    start_line: int
    end_line: int


@dataclass(frozen=True)
class CallableMeasurement:
    path: str
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
    measurements: list[CallableMeasurement] = []
    for region in executable_regions(path):
        tree = get_parser(region.language).parse(region.source)
        if tree.root_node.has_error:
            raise ValueError(f"unable to parse {path}: embedded {region.language} syntax tree contains errors")
        measurements.extend(_measure(node, region) for node in _callable_nodes(tree.root_node, region.language))
    return sorted(measurements, key=lambda value: (value.range.start_line, value.range.end_line, value.identity))


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _callable_nodes(root: Node, language: str) -> list[Node]:
    return [node for node in _walk(root) if node.type in CALLABLE_TYPES[language]]


def _measure(node: Node, region: ExecutableRegion) -> CallableMeasurement:
    start_node = _range_start_node(node, region.language)
    start_row, _ = region.original_point(start_node.start_point.row, start_node.start_point.column)
    end_row, _ = region.original_point(node.end_point.row, node.end_point.column)
    start_line = start_row + 1
    end_line = end_row + (1 if node.end_point.column > 0 else 0)
    return CallableMeasurement(
        path=region.original_path.as_posix(),
        language=region.language,
        identity=_identity(node, region),
        range=SourceRange(start_line, end_line),
        physical_loc=end_line - start_line + 1,
        nesting_depth=_nesting(node, region.language),
        cyclomatic_complexity=1 + _decision_count(node, region.language, region.source),
    )


def _range_start_node(node: Node, language: str) -> Node:
    if language == "python" and node.parent and node.parent.type == "decorated_definition":
        return node.parent
    if language in {"javascript", "typescript", "tsx"} and node.type in {"arrow_function", "function_expression"}:
        declarator = _ancestor(node, "variable_declarator")
        if declarator and declarator.child_by_field_name("value") == node:
            declaration_types = {"lexical_declaration", "variable_declaration"}
            return declarator.parent if declarator.parent and declarator.parent.type in declaration_types else declarator
    if language in {"typescript", "tsx"} and node.type == "method_definition":
        previous = node.prev_named_sibling
        first = node
        while previous and previous.type == "decorator":
            first = previous
            previous = previous.prev_named_sibling
        return first
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
    if language in {"kotlin", "csharp", "java"} and "constructor" in node.type:
        owner = _nearest_named_owner(node, language, source)
        return owner or "<constructor>"
    return "<anonymous>"


def _nearest_named_owner(node: Node, language: str, source: bytes) -> str | None:
    owner_types = {
        "python": {"class_definition"},
        "go": {"type_declaration", "type_spec"},
        "kotlin": {"class_declaration", "object_declaration"},
        "csharp": {"class_declaration", "struct_declaration", "record_declaration", "namespace_declaration", "file_scoped_namespace_declaration"},
        "java": {"class_declaration", "record_declaration", "enum_declaration"},
        "javascript": {"class_declaration"},
        "typescript": {"class_declaration"},
        "tsx": {"class_declaration"},
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


def _identity(node: Node, region: ExecutableRegion) -> str:
    language = region.language
    source = region.source
    path = region.original_path
    if language in {"javascript", "typescript", "tsx"}:
        return _javascript_identity(node, region)
    parts = [_name(node, language, source)]
    current = node.parent
    owner_types = {
        "python": {"class_definition", "function_definition"},
        "go": set(),
        "kotlin": {"class_declaration", "object_declaration", "function_declaration"},
        "csharp": {"namespace_declaration", "file_scoped_namespace_declaration", "class_declaration", "struct_declaration", "record_declaration", "method_declaration", "constructor_declaration", "local_function_statement"},
        "java": {"class_declaration", "record_declaration", "enum_declaration", "method_declaration", "constructor_declaration"},
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
        "java": {"package_declaration"},
    }.get(language, set())
    for child in root.named_children:
        if child.type in candidates:
            text = _text(child, source).replace("package", "", 1).replace("namespace", "", 1)
            return text.strip().rstrip(";")
    return ""


def _javascript_identity(node: Node, region: ExecutableRegion) -> str:
    source = region.source
    name = node.child_by_field_name("name")
    if node.type in {"arrow_function", "function_expression"}:
        declarator = _ancestor(node, "variable_declarator")
        if declarator and declarator.child_by_field_name("value") == node:
            name = declarator.child_by_field_name("name")
    parts = [_text(name, source) if name else _callback_name(node, region)]
    current = node.parent
    while current:
        if current.type == "class_declaration":
            owner = current.child_by_field_name("name")
            if owner:
                parts.append(_text(owner, source))
        elif current.type == "method_definition" and current is not node:
            owner = current.child_by_field_name("name")
            if owner:
                parts.append(_text(owner, source))
        elif current.type in {"function_declaration", "arrow_function", "function_expression"} and current is not node:
            owner = _javascript_lexical_name(current, source)
            if owner:
                parts.append(owner)
        current = current.parent
    if node.type == "method_definition" and not any(current.type == "class_declaration" for current in _ancestors(node)):
        object_name = _object_assignment_name(node, source)
        if object_name:
            parts.append(object_name)
    parts.append(region.original_path.stem)
    return ".".join(reversed(parts))


def _javascript_lexical_name(node: Node, source: bytes) -> str | None:
    name = node.child_by_field_name("name")
    if name:
        return _text(name, source)
    declarator = _ancestor(node, "variable_declarator")
    if declarator and declarator.child_by_field_name("value") == node:
        target = declarator.child_by_field_name("name")
        if target and target.type in {"identifier", "property_identifier"}:
            return _text(target, source)
    return None


def _callback_name(node: Node, region: ExecutableRegion) -> str:
    row, column = region.original_point(node.start_point.row, node.start_point.column)
    return f"<callback@{row + 1}:{column + 1}>"


def _object_assignment_name(node: Node, source: bytes) -> str | None:
    object_node = _ancestor(node, "object")
    declarator = _ancestor(object_node, "variable_declarator") if object_node else None
    if declarator:
        target = declarator.child_by_field_name("name")
        if target and target.type == "identifier":
            return _text(target, source)
    return None


def _ancestor(node: Node | None, node_type: str) -> Node | None:
    current = node.parent if node else None
    while current:
        if current.type == node_type:
            return current
        current = current.parent
    return None


def _ancestors(node: Node) -> Iterator[Node]:
    current = node.parent
    while current:
        yield current
        current = current.parent


def _nesting(callable_node: Node, language: str) -> int:
    def visit(node: Node, depth: int) -> int:
        maximum = depth
        for child in node.named_children:
            if (child.type in CALLABLE_TYPES[language] and child is not callable_node) or child.type in LAMBDA_TYPES[language]:
                continue
            increment = 1 if child.type in CONTROL_TYPES[language] else 0
            if child.type == "elif_clause" or _is_else_if(child, language):
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
            text = _text(node, source).strip()
            count += int(text.startswith("case ") and not text.endswith(":") and not _is_default_branch(node, source))
        if language == "java" and node.type in {"switch_block_statement_group", "switch_rule"}:
            text = _text(node, source).strip()
            count += int(text.startswith("case ") and not text.endswith(":"))
        if language in {"javascript", "typescript", "tsx"} and node.type == "switch_case":
            count += int(not _text(node, source).strip().endswith(":"))
    return count


def _is_else_if(node: Node, language: str) -> bool:
    if node.type not in {"if_statement", "if_expression"}:
        return False
    parent = node.parent
    if language == "kotlin":
        return bool(parent and parent.type == "control_structure_body" and parent.parent and parent.parent.type == "if_expression")
    if language in {"javascript", "typescript", "tsx"}:
        return bool(parent and parent.type == "else_clause")
    return bool(parent and parent.type == "if_statement" and parent.child_by_field_name("alternative") == node)


def _walk_without_nested_callables(root: Node, language: str) -> Iterator[Node]:
    yield root
    for child in root.named_children:
        if child.type in CALLABLE_TYPES[language] or child.type in LAMBDA_TYPES[language]:
            continue
        yield from _walk_without_nested_callables(child, language)


def _is_default_branch(node: Node, source: bytes) -> bool:
    text = _text(node, source).lstrip()
    return text.startswith(("default", "else", "case _", "case var _", "_ ->", "_ =>"))


def _short_circuit_operator_count(node: Node, source: bytes) -> int:
    direct_tokens = [_text(child, source) for child in node.children if not child.is_named]
    return sum(token in {"and", "or", "&&", "||"} for token in direct_tokens)
