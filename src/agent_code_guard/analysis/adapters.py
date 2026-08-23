"""Language-specific Tree-sitter extraction into normalized immutable facts."""

from __future__ import annotations

from typing import Iterator

from .facts import CallableFact, CallableKey, ControlFlowFact, DecisionFact, SourceRange
from .language_specs import (
    CALLABLE_TYPES, CONTROL_CATEGORIES, CONTROL_TYPES, DECISION_CATEGORIES, DECISION_TYPES,
    OPAQUE_LAMBDA_TYPES,
)
from .regions import ExecutableRegion


def extract_facts(root, region: ExecutableRegion) -> tuple[tuple[CallableFact, ...], tuple[ControlFlowFact, ...], tuple[DecisionFact, ...]]:
    nodes = [node for node in _walk(root) if node.type in CALLABLE_TYPES[region.language] and _has_body(node, region.language)]
    identities = {_node_key(node): _identity(node, region) for node in nodes}
    ranges = {_node_key(node): _callable_range(node, region) for node in nodes}
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
        if parent_node is None:
            containing = [candidate for candidate in nodes if candidate is not node
                          and ranges[_node_key(candidate)].start.byte_offset <= ranges[_node_key(node)].start.byte_offset
                          and ranges[_node_key(candidate)].end.byte_offset >= ranges[_node_key(node)].end.byte_offset]
            parent_node = min(containing, key=lambda candidate: ranges[_node_key(candidate)].physical_loc, default=None)
        node_key = _node_key(node)
        parent_key = keys.get(_node_key(parent_node)) if parent_node is not None else None
        callables.append(CallableFact(
            region.original_path, region.language, identity, ranges[node_key],
            identities.get(_node_key(parent_node)) if parent_node is not None else None,
            "callback" if _is_anonymous_callable(node, region) else ("nested" if parent_node else "callable"),
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
                increases = not (child.type in {"elif_clause", "else_if_clause"} or _is_else_if(child, language))
                controls.append(ControlFlowFact(
                    callable_key.identity, callable_key, _control_category(child.type, language), child.type,
                    child_range, parent_control, increases,
                ))
                if increases:
                    next_parent = child_range
            if child.type in DECISION_TYPES[language] and not _is_default_branch(child, region.source):
                decisions.append(DecisionFact(
                    callable_key.identity, callable_key, DECISION_CATEGORIES.get(child.type, child.type), child.type, child_range,
                ))
            for provider_kind, arm_range in _extra_switch_arm_ranges(child, language, region):
                decisions.append(DecisionFact(callable_key.identity, callable_key, "switch_arm", provider_kind, arm_range))
            for arm_range in _php_switch_arm_ranges(child, language, region):
                decisions.append(DecisionFact(
                    callable_key.identity, callable_key, "switch_arm", "case_statement", arm_range,
                ))
            guard = _pattern_guard(child, language)
            if guard is not None:
                decisions.append(DecisionFact(callable_key.identity, callable_key, "pattern_guard", guard.type,
                                              region.original_range(guard)))
            visit(child, next_parent)

    for structural_root in _structural_roots(callable_node, language):
        visit(structural_root, None)
    return controls, decisions


def _walk(node) -> Iterator:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _node_key(node) -> tuple[str, int, int]:
    return node.type, node.start_byte, node.end_byte


def _has_body(node, language: str) -> bool:
    if language in {"typescript", "tsx"} and node.type in {"function_declaration", "method_definition"}:
        return node.child_by_field_name("body") is not None
    if language == "swift" and node.type == "protocol_function_declaration":
        return any(child.type == "statements" for child in node.named_children)
    if language == "dart" and node.type in {"function_signature", "method_signature"}:
        return _dart_body(node) is not None and not any(parent.type == "lambda_expression" for parent in _ancestors(node))
    return True


def _range_end_node(node, language: str):
    return _dart_body(node) if language == "dart" and _dart_body(node) is not None else node


def _callable_range(node, region: ExecutableRegion) -> SourceRange:
    """Snapshot provider points once before mapping them to original source."""
    start_row, start_column = _range_start_node(node, region.language).start_point
    end_row, end_column = _range_end_node(node, region.language).end_point
    return SourceRange(
        region.original_point(start_row, start_column),
        region.original_point(end_row, end_column),
    )


def _structural_roots(node, language: str):
    body = _dart_body(node) if language == "dart" else None
    return (body,) if body is not None else (node,)


def _dart_body(node):
    if node.type not in {"function_signature", "method_signature"}:
        return None
    sibling = node.next_named_sibling
    return sibling if sibling is not None and sibling.type == "function_body" else None


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
    if language == "cpp" and node.parent and node.parent.type == "template_declaration":
        return node.parent
    if language in {"cpp", "php", "swift", "dart", "rust"} and _is_closure(node, language):
        owner = _assigned_closure_owner(node, language)
        if owner is not None:
            return owner
    if language == "swift" and node.type == "protocol_function_declaration" and node.prev_named_sibling:
        previous = node.prev_named_sibling
        if previous.type == "protocol_function_declaration" and previous.child_by_field_name("name") is not None:
            return previous
    return node


def _identity(node, region: ExecutableRegion) -> str:
    if region.language in {"javascript", "typescript", "tsx"}:
        return _javascript_identity(node, region)
    if region.language in {"cpp", "rust", "php", "swift", "dart"}:
        return _second_wave_identity(node, region)
    if node.type in MAINSTREAM_LAMBDA_TYPES[region.language]:
        return _mainstream_lambda_identity(node, region)
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


def _second_wave_identity(node, region: ExecutableRegion) -> str:
    language, source = region.language, region.source
    name = _second_wave_name(node, language, source)
    parts = [name or _callback_name(node, region)]
    owner_types = {
        "cpp": {"namespace_definition", "class_specifier", "struct_specifier", "union_specifier", "function_definition"},
        "rust": {"trait_item", "impl_item", "function_item"},
        "php": {"namespace_definition", "class_declaration", "trait_declaration", "interface_declaration", "function_definition", "method_declaration"},
        "swift": {"class_declaration", "struct_declaration", "protocol_declaration", "function_declaration", "init_declaration"},
        "dart": {"class_definition", "function_signature", "constructor_signature", "lambda_expression"},
    }[language]
    for current in _ancestors(node):
        if current.type not in owner_types:
            continue
        owner = _second_wave_name(current, language, source)
        if owner:
            parts.append(owner)
    parts.append(region.original_path.stem)
    return ".".join(reversed(parts))


def _second_wave_name(node, language: str, source: bytes) -> str | None:
    name = node.child_by_field_name("name")
    if language == "cpp" and node.type == "function_definition":
        declarator = node.child_by_field_name("declarator")
        name = _deep_named_child(declarator, {"identifier", "field_identifier", "destructor_name", "operator_name"})
    elif language == "cpp" and node.type == "lambda_expression":
        name = _assigned_name(node, language)
    elif language == "rust" and node.type == "closure_expression":
        name = _assigned_name(node, language)
    elif language == "php" and node.type in {"arrow_function", "anonymous_function"}:
        name = _assigned_name(node, language)
    elif language == "swift" and node.type == "init_declaration":
        return "init"
    elif language == "swift" and node.type == "protocol_function_declaration" and name is None:
        previous = node.prev_named_sibling
        name = previous.child_by_field_name("name") if previous is not None else None
    elif language == "swift" and node.type == "lambda_literal":
        name = _assigned_name(node, language)
    elif language == "dart" and node.type in {"function_expression", "lambda_expression"}:
        signature = next((child for child in node.named_children if child.type == "function_signature"), None)
        name = signature.child_by_field_name("name") if signature is not None else _assigned_name(node, language)
    elif language == "dart" and node.type == "method_signature":
        signature = next((child for child in node.named_children
                          if child.type in {"function_signature", "constructor_signature"}), None)
        name = signature.child_by_field_name("name") if signature is not None else None
    elif language == "dart" and node.type == "class_definition":
        name = node.child_by_field_name("name")
    elif language == "rust" and node.type == "impl_item":
        name = node.child_by_field_name("type")
    if name is None and language == "swift" and node.type == "class_declaration":
        name = next((child for child in node.named_children if child.type in {"type_identifier", "user_type"}), None)
    return _text(name, source).lstrip("$") if name is not None else None


def _deep_named_child(node, types: set[str]):
    if node is None:
        return None
    if node.type in types:
        return node
    for child in node.named_children:
        found = _deep_named_child(child, types)
        if found is not None:
            return found
    return None


def _is_closure(node, language: str) -> bool:
    return node.type in {
        "cpp": {"lambda_expression"}, "rust": {"closure_expression"},
        "php": {"arrow_function", "anonymous_function"},
        "swift": {"lambda_literal"}, "dart": {"function_expression", "lambda_expression"},
    }.get(language, set())


def _assigned_name(node, language: str):
    owner = _assigned_closure_owner(node, language)
    if owner is None:
        return None
    candidates = {
        "cpp": {"identifier"}, "rust": {"identifier"}, "php": {"variable_name"},
        "swift": {"pattern"}, "dart": {"identifier"},
    }[language]
    return _deep_named_child(owner, candidates)


def _assigned_closure_owner(node, language: str):
    if language == "php":
        assignment = _ancestor(node, "assignment_expression")
        if assignment is None or assignment.child_by_field_name("right") != node:
            return None
        return assignment.parent if assignment.parent and assignment.parent.type == "expression_statement" else assignment
    owner_types = {
        "cpp": {"declaration"}, "rust": {"let_declaration"},
        "swift": {"property_declaration"}, "dart": {"local_variable_declaration"},
    }[language]
    current = node.parent
    while current and current.type not in CALLABLE_TYPES[language]:
        if current.type in owner_types:
            return current
        current = current.parent
    return None


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
    row, column = node.start_point
    point = region.original_point(row, column)
    return f"<callback@{point.line}:{point.byte_column}>"


MAINSTREAM_LAMBDA_TYPES = {
    "python": {"lambda"}, "go": {"func_literal"},
    "kotlin": {"lambda_literal", "anonymous_function"},
    "csharp": {"lambda_expression", "anonymous_method_expression"},
    "java": {"lambda_expression"},
}


def _mainstream_lambda_identity(node, region: ExecutableRegion) -> str:
    parts = [_callback_name(node, region)]
    for current in _ancestors(node):
        if current.type in MAINSTREAM_LAMBDA_TYPES[region.language]:
            parts.append(_callback_name(current, region))
        elif current.type in CALLABLE_TYPES[region.language]:
            name = _name_node(current, region.language)
            if name is not None:
                parts.append(_text(name, region.source))
        elif current.type in {"class_definition", "class_declaration", "object_declaration", "struct_declaration", "record_declaration", "enum_declaration"}:
            name = _name_node(current, region.language)
            if name is not None:
                parts.append(_text(name, region.source))
    parts.append(region.original_path.stem if region.language == "python" else _package_or_namespace(node, region.language, region.source))
    return ".".join(reversed([part for part in parts if part]))


def _is_anonymous_callable(node, region: ExecutableRegion) -> bool:
    if region.language in {"javascript", "typescript", "tsx"}:
        return _javascript_lexical_name(node, region.source) is None
    if node.type in MAINSTREAM_LAMBDA_TYPES.get(region.language, set()):
        return True
    return _is_closure(node, region.language) and _second_wave_name(node, region.language, region.source) is None


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
    if language == "php":
        return bool(parent and parent.type == "else_if_clause")
    if language == "swift":
        return bool(parent and parent.type == "if_statement")
    if language == "rust":
        return bool(parent and parent.type == "else_clause")
    return bool(parent and parent.type == "if_statement" and parent.child_by_field_name("alternative") == node)


def _is_default_branch(node, source: bytes) -> bool:
    if node.type == "else_if_clause":
        return False
    return _text(node, source).lstrip().startswith(("default", "else", "case _", "case var _", "_ ->", "_ =>"))


def _control_category(provider_kind: str, language: str) -> str:
    if language == "swift" and provider_kind == "do_statement":
        return "exception"
    return CONTROL_CATEGORIES.get(provider_kind, provider_kind)


def _extra_switch_arm_ranges(node, language: str, region: ExecutableRegion) -> tuple[tuple[str, SourceRange], ...]:
    if language == "java" and node.type == "switch_rule":
        return () if _is_default_branch(node, region.source) else ((node.type, region.original_range(node)),)

    clauses: tuple
    provider_kind: str
    if language == "cpp" and node.type == "compound_statement" and node.parent.type == "switch_statement":
        clauses = tuple(_cpp_switch_clauses(node))
        provider_kind = "case_statement"
    elif language == "csharp" and node.type == "switch_body":
        clauses = tuple(child for child in node.named_children if child.type == "switch_section")
        provider_kind = "switch_section"
    elif language == "java" and node.type == "switch_block":
        clauses = tuple(child for child in node.named_children if child.type == "switch_block_statement_group")
        provider_kind = "switch_block_statement_group"
    elif language in {"javascript", "typescript", "tsx"} and node.type == "switch_body":
        clauses = tuple(child for child in node.named_children if child.type in {"switch_case", "switch_default"})
        provider_kind = "switch_case"
    else:
        return ()

    ranges: list[SourceRange] = []
    pending_case = None
    for index, clause in enumerate(clauses):
        non_default = not _is_default_branch(clause, region.source)
        next_clause = clauses[index + 1] if language == "cpp" and index + 1 < len(clauses) else None
        if not _classic_switch_clause_has_body(clause, next_clause):
            if non_default and pending_case is None:
                pending_case = clause
            continue

        representative = pending_case or (clause if non_default else None)
        if representative is not None:
            ranges.append(region.original_range(representative))
        pending_case = None
    return tuple((provider_kind, arm_range) for arm_range in ranges)


def _cpp_switch_clauses(node) -> Iterator:
    for child in node.named_children:
        if child.type == "switch_statement":
            continue
        if child.type == "case_statement":
            yield child
        yield from _cpp_switch_clauses(child)


def _classic_switch_clause_has_body(clause, next_clause=None) -> bool:
    colon = next((child for child in clause.children if child.type == ":"), None)
    if colon is None:
        return False
    for child in clause.children:
        if not child.is_named or child.start_byte < colon.end_byte or child.type in {"comment", "empty_statement"}:
            continue
        if next_clause is not None and child.start_byte < next_clause.start_byte < child.end_byte:
            if child.type == "compound_statement" or child.type.startswith("preproc_"):
                return _cpp_wrapper_has_executable_before(child, next_clause.start_byte)
            return True
        return True
    return False


def _cpp_wrapper_has_executable_before(node, limit: int) -> bool:
    preprocessor_wrapper = node.type.startswith("preproc_")
    for child in node.named_children:
        if child.start_byte >= limit or child.type in {"case_statement", "comment", "empty_statement"}:
            continue
        if child.type == "compound_statement" or child.type.startswith("preproc_"):
            if _cpp_wrapper_has_executable_before(child, limit):
                return True
        elif not preprocessor_wrapper or child.type.endswith(("_statement", "_declaration")) or child.type == "declaration":
            return True
    return False


def _php_switch_arm_ranges(node, language: str, region: ExecutableRegion) -> tuple[SourceRange, ...]:
    """Normalize PHP case-label groups into executable non-default arms."""
    if language != "php" or node.type != "switch_block":
        return ()

    ranges: list[SourceRange] = []
    pending_case = None
    for clause in (child for child in node.named_children
                   if child.type in {"case_statement", "default_statement"}):
        value = clause.child_by_field_name("value")
        body = [child for child in clause.named_children
                if child != value and child.type not in {"comment", "empty_statement"}]
        if not body:
            if clause.type == "case_statement" and pending_case is None:
                pending_case = clause
            continue

        representative = pending_case or (clause if clause.type == "case_statement" else None)
        if representative is not None:
            ranges.append(region.original_range(representative))
        pending_case = None
    return tuple(ranges)


def _pattern_guard(node, language: str):
    if language == "rust" and node.type == "match_arm":
        pattern = node.child_by_field_name("pattern")
        return pattern.child_by_field_name("condition") if pattern is not None else None
    if language == "swift" and node.type == "switch_entry":
        children = node.named_children
        for index, child in enumerate(children):
            if child.type == "where_keyword" and index + 1 < len(children):
                return children[index + 1]
    return None
