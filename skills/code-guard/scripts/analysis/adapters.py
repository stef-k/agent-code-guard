"""Language-specific Tree-sitter extraction into normalized immutable facts."""

from __future__ import annotations

from typing import Iterator

from .facts import CallableFact, CallableKey, ControlFlowFact, DecisionFact, SourceRange
from .regions import ExecutableRegion

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

OPAQUE_LAMBDA_TYPES = {
    "python": {"lambda"}, "go": {"func_literal"},
    "kotlin": {"lambda_literal", "anonymous_function"},
    "csharp": {"lambda_expression", "anonymous_method_expression"},
    "java": {"lambda_expression"}, "javascript": set(), "typescript": set(), "tsx": set(),
}

CONTROL_CATEGORIES = {
    "if_statement": "condition", "if_expression": "condition", "elif_clause": "condition",
    "for_statement": "loop", "foreach_statement": "loop", "enhanced_for_statement": "loop",
    "for_in_statement": "loop", "while_statement": "loop", "do_statement": "loop",
    "do_while_statement": "loop", "match_statement": "selection", "when_expression": "selection",
    "switch_statement": "selection", "switch_expression": "selection",
    "expression_switch_statement": "selection", "type_switch_statement": "selection",
    "select_statement": "selection", "try_statement": "exception", "try_expression": "exception",
}

CONTROL_TYPES = {
    "python": {"if_statement", "elif_clause", "for_statement", "while_statement", "match_statement", "try_statement"},
    "go": {"if_statement", "for_statement", "expression_switch_statement", "type_switch_statement", "select_statement"},
    "kotlin": {"if_expression", "for_statement", "while_statement", "do_while_statement", "when_expression", "try_expression"},
    "csharp": {"if_statement", "for_statement", "foreach_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "java": {"if_statement", "for_statement", "enhanced_for_statement", "while_statement", "do_statement", "switch_expression", "try_statement"},
    "javascript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "typescript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "tsx": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
}

DECISION_CATEGORIES = {
    "if_statement": "condition", "if_expression": "condition", "elif_clause": "condition",
    "for_statement": "loop", "foreach_statement": "loop", "enhanced_for_statement": "loop",
    "for_in_statement": "loop", "while_statement": "loop", "do_statement": "loop", "do_while_statement": "loop",
    "except_clause": "catch", "catch_clause": "catch", "catch_block": "catch",
    "conditional_expression": "ternary", "ternary_expression": "ternary",
    "list_comprehension": "comprehension", "set_comprehension": "comprehension",
    "dictionary_comprehension": "comprehension", "generator_expression": "comprehension",
    "case_clause": "switch_arm", "expression_case": "switch_arm", "type_case": "switch_arm",
    "communication_case": "switch_arm", "when_entry": "switch_arm", "switch_expression_arm": "switch_arm",
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


def extract_facts(root, region: ExecutableRegion) -> tuple[tuple[CallableFact, ...], tuple[ControlFlowFact, ...], tuple[DecisionFact, ...]]:
    nodes = [node for node in _walk(root) if node.type in CALLABLE_TYPES[region.language] and _has_body(node, region.language)]
    identities = {_node_key(node): _identity(node, region) for node in nodes}
    ranges = {
        _node_key(node): SourceRange(
            region.original_point(_range_start_node(node, region.language).start_point.row,
                                  _range_start_node(node, region.language).start_point.column),
            region.original_point(node.end_point.row, node.end_point.column),
        ) for node in nodes
    }
    keys = {
        node_key: CallableKey(region.original_path, region.language, identity, ranges[node_key])
        for node_key, identity in identities.items()
    }
    callables: list[CallableFact] = []
    controls: list[ControlFlowFact] = []
    decisions: list[DecisionFact] = []
    for node in nodes:
        identity = identities[_node_key(node)]
        parent_node = next((ancestor for ancestor in _ancestors(node) if _node_key(ancestor) in identities), None)
        node_key = _node_key(node)
        parent_key = keys.get(_node_key(parent_node)) if parent_node is not None else None
        callables.append(CallableFact(
            region.original_path, region.language, identity, ranges[node_key],
            identities.get(_node_key(parent_node)) if parent_node is not None else None,
            "callback" if _is_anonymous_js_callable(node, region) else ("nested" if parent_node else "callable"),
            keys[node_key], parent_key,
        ))
        extracted_controls, extracted_decisions = _structural_facts(node, keys[node_key], region)
        controls.extend(extracted_controls)
        decisions.extend(extracted_decisions)
    key = lambda fact: (fact.source_range.start.byte_offset, fact.source_range.end.byte_offset)
    return tuple(sorted(callables, key=key)), tuple(sorted(controls, key=key)), tuple(sorted(decisions, key=key))


def _structural_facts(callable_node, callable_key: CallableKey, region: ExecutableRegion):
    controls: list[ControlFlowFact] = []
    decisions: list[DecisionFact] = []
    language = region.language

    def visit(node, parent_control: SourceRange | None) -> None:
        for child in node.named_children:
            if child.type in CALLABLE_TYPES[language] or child.type in OPAQUE_LAMBDA_TYPES[language]:
                continue
            child_range = region.original_range(child)
            next_parent = parent_control
            if child.type in CONTROL_TYPES[language]:
                increases = not (child.type == "elif_clause" or _is_else_if(child, language))
                controls.append(ControlFlowFact(
                    callable_key.identity, callable_key, CONTROL_CATEGORIES.get(child.type, child.type), child.type,
                    child_range, parent_control, increases,
                ))
                if increases:
                    next_parent = child_range
            if child.type in DECISION_TYPES[language] and not _is_default_branch(child, region.source):
                decisions.append(DecisionFact(
                    callable_key.identity, callable_key, DECISION_CATEGORIES.get(child.type, child.type), child.type, child_range,
                ))
            if child.type in {"boolean_operator", "conjunction_expression", "disjunction_expression", "binary_expression"}:
                for _ in range(_short_circuit_count(child, region.source)):
                    decisions.append(DecisionFact(callable_key.identity, callable_key, "short_circuit_boolean", child.type, child_range))
            for arm_range in _extra_switch_arm_ranges(child, language, region):
                decisions.append(DecisionFact(callable_key.identity, callable_key, "switch_arm", child.type, arm_range))
            visit(child, next_parent)

    visit(callable_node, None)
    return controls, decisions


def _walk(node) -> Iterator:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _node_key(node) -> tuple[str, int, int]:
    return node.type, node.start_byte, node.end_byte


def _has_body(node, language: str) -> bool:
    if language not in {"typescript", "tsx"} or node.type not in {"function_declaration", "method_definition"}:
        return True
    return node.child_by_field_name("body") is not None


def _range_start_node(node, language: str):
    if language == "python" and node.parent and node.parent.type == "decorated_definition":
        return node.parent
    if language in {"javascript", "typescript", "tsx"} and node.type in {"arrow_function", "function_expression"}:
        declarator = _ancestor(node, "variable_declarator")
        if declarator and declarator.child_by_field_name("value") == node:
            return declarator.parent if declarator.parent and declarator.parent.type in {"lexical_declaration", "variable_declaration"} else declarator
    if language in {"typescript", "tsx"} and node.type == "method_definition":
        first = node
        previous = node.prev_named_sibling
        while previous and previous.type == "decorator":
            first, previous = previous, previous.prev_named_sibling
        return first
    return node


def _identity(node, region: ExecutableRegion) -> str:
    if region.language in {"javascript", "typescript", "tsx"}:
        return _javascript_identity(node, region)
    source, language = region.source, region.language
    parts = [_name(node, language, source)]
    owner_types = {
        "python": {"class_definition", "function_definition"}, "go": set(),
        "kotlin": {"class_declaration", "object_declaration", "function_declaration"},
        "csharp": {"namespace_declaration", "file_scoped_namespace_declaration", "class_declaration", "struct_declaration", "record_declaration", "method_declaration", "constructor_declaration", "local_function_statement"},
        "java": {"class_declaration", "record_declaration", "enum_declaration", "method_declaration", "constructor_declaration"},
    }[language]
    for current in _ancestors(node):
        if current.type in owner_types:
            name = _name_node(current, language)
            if name:
                parts.append(_text(name, source))
    if language == "go":
        receiver = node.child_by_field_name("receiver")
        if receiver:
            words = _text(receiver, source).replace("(", "").replace(")", "").replace("*", "").split()
            parts.append(words[-1] if words else "receiver")
    parts.append(region.original_path.stem if language == "python" else _package_or_namespace(node, language, source))
    return ".".join(reversed([part for part in parts if part]))


def _javascript_identity(node, region: ExecutableRegion) -> str:
    source = region.source
    name = node.child_by_field_name("name")
    if node.type in {"arrow_function", "function_expression"}:
        declarator = _ancestor(node, "variable_declarator")
        if declarator and declarator.child_by_field_name("value") == node:
            name = declarator.child_by_field_name("name")
    parts = [_text(name, source) if name else _callback_name(node, region)]
    for current in _ancestors(node):
        owner = None
        if current.type == "class_declaration":
            owner = current.child_by_field_name("name")
        elif current.type == "method_definition" and current is not node:
            owner = current.child_by_field_name("name")
        elif current.type in {"function_declaration", "arrow_function", "function_expression"} and current is not node:
            lexical = _javascript_lexical_name(current, source)
            if lexical:
                parts.append(lexical)
        if owner:
            parts.append(_text(owner, source))
    if node.type == "method_definition" and not any(value.type == "class_declaration" for value in _ancestors(node)):
        object_name = _object_assignment_name(node, source)
        if object_name:
            parts.append(object_name)
    parts.append(region.original_path.stem)
    return ".".join(reversed(parts))


def _name(node, language: str, source: bytes) -> str:
    name = _name_node(node, language)
    if name:
        return _text(name, source)
    if language in {"kotlin", "csharp", "java"} and "constructor" in node.type:
        for owner in _ancestors(node):
            if owner.type in {"class_declaration", "object_declaration", "struct_declaration", "record_declaration", "enum_declaration"}:
                owner_name = _name_node(owner, language)
                if owner_name:
                    return _text(owner_name, source)
    return "<anonymous>"


def _name_node(node, language: str):
    name = node.child_by_field_name("name")
    if name is None and language == "kotlin":
        name = next((child for child in node.named_children if child.type in {"simple_identifier", "type_identifier"}), None)
    return name


def _package_or_namespace(node, language: str, source: bytes) -> str:
    root = node
    while root.parent:
        root = root.parent
    types = {"go": {"package_clause"}, "kotlin": {"package_header"}, "csharp": {"file_scoped_namespace_declaration"}, "java": {"package_declaration"}}.get(language, set())
    for child in root.named_children:
        if child.type in types:
            return _text(child, source).replace("package", "", 1).replace("namespace", "", 1).strip().rstrip(";")
    return ""


def _javascript_lexical_name(node, source: bytes) -> str | None:
    name = node.child_by_field_name("name")
    if name:
        return _text(name, source)
    declarator = _ancestor(node, "variable_declarator")
    if declarator and declarator.child_by_field_name("value") == node:
        target = declarator.child_by_field_name("name")
        if target and target.type in {"identifier", "property_identifier"}:
            return _text(target, source)
    return None


def _callback_name(node, region: ExecutableRegion) -> str:
    point = region.original_point(node.start_point.row, node.start_point.column)
    return f"<callback@{point.line}:{point.byte_column}>"


def _is_anonymous_js_callable(node, region: ExecutableRegion) -> bool:
    return region.language in {"javascript", "typescript", "tsx"} and _javascript_lexical_name(node, region.source) is None


def _object_assignment_name(node, source: bytes) -> str | None:
    object_node = _ancestor(node, "object")
    declarator = _ancestor(object_node, "variable_declarator") if object_node else None
    target = declarator.child_by_field_name("name") if declarator else None
    return _text(target, source) if target and target.type == "identifier" else None


def _ancestor(node, node_type: str):
    current = node.parent if node else None
    while current:
        if current.type == node_type:
            return current
        current = current.parent
    return None


def _ancestors(node) -> Iterator:
    current = node.parent
    while current:
        yield current
        current = current.parent


def _text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _is_else_if(node, language: str) -> bool:
    if node.type not in {"if_statement", "if_expression"}:
        return False
    parent = node.parent
    if language == "kotlin":
        return bool(parent and parent.type == "control_structure_body" and parent.parent and parent.parent.type == "if_expression")
    if language in {"javascript", "typescript", "tsx"}:
        return bool(parent and parent.type == "else_clause")
    return bool(parent and parent.type == "if_statement" and parent.child_by_field_name("alternative") == node)


def _is_default_branch(node, source: bytes) -> bool:
    return _text(node, source).lstrip().startswith(("default", "else", "case _", "case var _", "_ ->", "_ =>"))


def _short_circuit_count(node, source: bytes) -> int:
    return sum(_text(child, source) in {"and", "or", "&&", "||"} for child in node.children if not child.is_named)


def _extra_switch_arm_ranges(node, language: str, region: ExecutableRegion) -> tuple[SourceRange, ...]:
    eligible = (
        (language == "csharp" and node.type == "switch_section")
        or (language == "java" and node.type in {"switch_block_statement_group", "switch_rule"})
        or (language in {"javascript", "typescript", "tsx"} and node.type == "switch_case")
    )
    if not eligible:
        return ()
    labels = [child for child in node.named_children if child.type in {
        "case_switch_label", "case_pattern_switch_label", "switch_label", "case",
    }]
    if labels:
        return tuple(region.original_range(label) for label in labels if not _is_default_branch(label, region.source))
    return () if _is_default_branch(node, region.source) else (region.original_range(node),)
