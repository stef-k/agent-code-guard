"""Language-specific executable control and decision normalization."""

from __future__ import annotations

from typing import Iterator, NamedTuple

from .language_specs import CONTROL_CATEGORIES, CONTROL_TYPES, DECISION_CATEGORIES, DECISION_TYPES
from .syntax_nodes import node_text

__all__ = ["control_semantics", "normalized_decisions"]


class _ControlSemantics(NamedTuple):
    category: str
    increases_nesting: bool


class _NormalizedDecision(NamedTuple):
    category: str
    provider_kind: str
    node: object


def control_semantics(node, language: str) -> _ControlSemantics | None:
    if node.type not in CONTROL_TYPES[language] or not _is_meaningful_control(node, language):
        return None
    increases = not (node.type in {"elif_clause", "else_if_clause"} or _is_else_if(node, language))
    category = "exception" if language == "swift" and node.type == "do_statement" else CONTROL_CATEGORIES.get(node.type, node.type)
    return _ControlSemantics(category, increases)


def normalized_decisions(node, language: str, source: bytes) -> tuple[_NormalizedDecision, ...]:
    decisions: list[_NormalizedDecision] = []
    if node.type in DECISION_TYPES[language] and not _is_default_branch(node, source, language):
        decisions.append(_NormalizedDecision(DECISION_CATEGORIES.get(node.type, node.type), node.type, node))
    decisions.extend(
        _NormalizedDecision("switch_arm", provider_kind, representative)
        for provider_kind, representative in _extra_switch_arm_ranges(node, language, source)
    )
    decisions.extend(
        _NormalizedDecision("switch_arm", "case_statement", representative)
        for representative in _php_switch_arm_ranges(node, language)
    )
    guard = _pattern_guard(node, language)
    if guard is not None:
        decisions.append(_NormalizedDecision("pattern_guard", guard.type, guard))
    return tuple(decisions)


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


def _is_default_branch(node, source: bytes, language: str | None = None) -> bool:
    if node.type == "else_if_clause":
        return False
    if language == "python" and node.type == "case_clause" and node.child_by_field_name("guard") is not None:
        return False
    return node_text(node, source).lstrip().startswith(("default", "else", "case _", "case var _", "_ ->", "_ =>"))


def _is_meaningful_control(node, language: str) -> bool:
    if language == "swift" and node.type == "do_statement":
        return any(child.type == "catch_block" for child in node.named_children)
    return True


def _extra_switch_arm_ranges(node, language: str, source: bytes) -> tuple[tuple[str, object], ...]:
    if language == "java" and node.type == "switch_rule":
        return () if _is_default_branch(node, source) else ((node.type, node),)

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

    representatives: list[object] = []
    pending_case = None
    for index, clause in enumerate(clauses):
        non_default = not _is_default_branch(clause, source)
        next_clause = clauses[index + 1] if language == "cpp" and index + 1 < len(clauses) else None
        if not _classic_switch_clause_has_body(clause, next_clause):
            if non_default and pending_case is None:
                pending_case = clause
            continue

        representative = pending_case or (clause if non_default else None)
        if representative is not None:
            representatives.append(representative)
        pending_case = None
    return tuple((provider_kind, representative) for representative in representatives)


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


def _php_switch_arm_ranges(node, language: str) -> tuple[object, ...]:
    """Normalize PHP case-label groups into executable non-default arms."""
    if language != "php" or node.type != "switch_block":
        return ()

    representatives: list[object] = []
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
            representatives.append(representative)
        pending_case = None
    return tuple(representatives)


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
