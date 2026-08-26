"""Language-specific Tree-sitter extraction into normalized immutable facts."""

from __future__ import annotations

from typing import Iterator

from .callable_identity import callable_identity, callable_source_start, is_anonymous_callable
from .facts import CallableFact, CallableKey, ControlFlowFact, DecisionFact, SourceRange
from .language_specs import (
    CALLABLE_TYPES, CONTROL_CATEGORIES, CONTROL_TYPES, DECISION_CATEGORIES, DECISION_TYPES,
    OPAQUE_LAMBDA_TYPES,
)
from .regions import ExecutableRegion


def extract_facts(root, region: ExecutableRegion) -> tuple[tuple[CallableFact, ...], tuple[ControlFlowFact, ...], tuple[DecisionFact, ...]]:
    nodes = [node for node in _walk(root) if node.type in CALLABLE_TYPES[region.language] and _has_body(node, region.language)]
    identities = {_node_key(node): callable_identity(node, region) for node in nodes}
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
        parent_node = _parent_callable(node, identities)
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
            "callback" if is_anonymous_callable(node, region) else ("nested" if parent_node else "callable"),
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
            if child.type in CONTROL_TYPES[language] and _is_meaningful_control(child, language):
                increases = not (child.type in {"elif_clause", "else_if_clause"} or _is_else_if(child, language))
                controls.append(ControlFlowFact(
                    callable_key.identity, callable_key, _control_category(child.type, language), child.type,
                    child_range, parent_control, increases,
                ))
                if increases:
                    next_parent = child_range
            if child.type in DECISION_TYPES[language] and not _is_default_branch(child, region.source, language):
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


def _parent_callable(node, identities):
    current = node.parent
    while current:
        if _node_key(current) in identities:
            return current
        current = current.parent
    return None


def _has_body(node, language: str) -> bool:
    if language in {"typescript", "tsx"} and node.type in {"function_declaration", "method_definition"}:
        return node.child_by_field_name("body") is not None
    if language == "swift" and node.type == "protocol_function_declaration":
        return any(child.type == "statements" for child in node.named_children)
    if language == "dart" and node.type in {"function_signature", "method_signature"}:
        current = node.parent
        while current:
            if current.type == "lambda_expression":
                return False
            current = current.parent
        return _dart_body(node) is not None
    return True


def _range_end_node(node, language: str):
    return _dart_body(node) if language == "dart" and _dart_body(node) is not None else node


def _callable_range(node, region: ExecutableRegion) -> SourceRange:
    """Snapshot provider points once before mapping them to original source."""
    start_row, start_column = callable_source_start(node, region.language).start_point
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


def _text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _is_default_branch(node, source: bytes, language: str | None = None) -> bool:
    if node.type == "else_if_clause":
        return False
    if language == "python" and node.type == "case_clause" and node.child_by_field_name("guard") is not None:
        return False
    return _text(node, source).lstrip().startswith(("default", "else", "case _", "case var _", "_ ->", "_ =>"))


def _control_category(provider_kind: str, language: str) -> str:
    if language == "swift" and provider_kind == "do_statement":
        return "exception"
    return CONTROL_CATEGORIES.get(provider_kind, provider_kind)


def _is_meaningful_control(node, language: str) -> bool:
    if language == "swift" and node.type == "do_statement":
        return any(child.type == "catch_block" for child in node.named_children)
    return True


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
    if language == "python" and node.type == "case_clause":
        guard = node.child_by_field_name("guard")
        return guard.named_children[0] if guard is not None and guard.named_children else None
    if language == "csharp" and node.type == "switch_expression_arm":
        clause = next((child for child in node.named_children if child.type == "when_clause"), None)
        return clause.named_children[0] if clause is not None and clause.named_children else None
    if language == "rust" and node.type == "match_arm":
        pattern = node.child_by_field_name("pattern")
        return pattern.child_by_field_name("condition") if pattern is not None else None
    if language == "swift" and node.type == "switch_entry":
        children = node.named_children
        for index, child in enumerate(children):
            if child.type == "where_keyword" and index + 1 < len(children):
                return children[index + 1]
    return None
