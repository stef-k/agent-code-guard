"""Language-specific Tree-sitter extraction into normalized immutable facts."""

from __future__ import annotations

from typing import Iterator

from .branch_normalization import control_semantics, normalized_decisions
from .callable_identity import callable_identity, callable_source_start, is_anonymous_callable
from .facts import CallableFact, CallableKey, ControlFlowFact, DecisionFact, SourceRange
from .language_specs import CALLABLE_TYPES, OPAQUE_LAMBDA_TYPES
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
            next_parent = parent_control
            semantics = control_semantics(child, language)
            if semantics is not None:
                child_range = region.original_range(child)
                controls.append(ControlFlowFact(
                    callable_key.identity, callable_key, semantics.category, child.type,
                    child_range, parent_control, semantics.increases_nesting,
                ))
                if semantics.increases_nesting:
                    next_parent = child_range
            for decision in normalized_decisions(child, language, region.source):
                decisions.append(DecisionFact(
                    callable_key.identity, callable_key, decision.category, decision.provider_kind,
                    region.original_range(decision.node),
                ))
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
