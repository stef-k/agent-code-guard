"""Narrow compatibility correction for upstream C# contextual-keyword errors."""

from __future__ import annotations


_CONTEXTUAL_KEYWORD = b"async"
_NEUTRAL_IDENTIFIER = b"azync"


def corrected_csharp_root(provider, source: bytes, first_tree):
    """Return one verified corrected root, or ``None`` when correction is unsafe."""
    problems = tuple(_problem_nodes(first_tree.root_node))
    if not problems:
        return None

    token_offsets: set[int] = set()
    for problem in problems:
        candidates = _contained_unescaped_tokens(source, problem.start_byte, problem.end_byte)
        if len(candidates) != 1:
            return None
        token_offsets.add(candidates[0])

    corrected = bytearray(source)
    for offset in token_offsets:
        corrected[offset:offset + len(_CONTEXTUAL_KEYWORD)] = _NEUTRAL_IDENTIFIER
    corrected_source = bytes(corrected)
    if len(corrected_source) != len(source) or _newline_offsets(corrected_source) != _newline_offsets(source):
        return None

    retry_tree = provider.parse("csharp", corrected_source)
    if retry_tree.root_node.has_error or any(_problem_nodes(retry_tree.root_node)):
        return None
    if not all(_has_authorized_role(retry_tree.root_node, offset) for offset in token_offsets):
        return None
    return retry_tree.root_node


def _problem_nodes(node):
    if node.is_error or node.is_missing:
        yield node
    for child in node.children:
        yield from _problem_nodes(child)


def _contained_unescaped_tokens(source: bytes, start: int, end: int) -> tuple[int, ...]:
    offsets: list[int] = []
    position = source.find(_CONTEXTUAL_KEYWORD, start, end)
    while position >= 0:
        token_end = position + len(_CONTEXTUAL_KEYWORD)
        if token_end <= end and _is_token_boundary(source, position, token_end):
            offsets.append(position)
        position = source.find(_CONTEXTUAL_KEYWORD, position + 1, end)
    return tuple(offsets)


def _is_token_boundary(source: bytes, start: int, end: int) -> bool:
    before = source[start - 1] if start else None
    after = source[end] if end < len(source) else None
    return before != ord("@") and not _identifier_byte(before) and not _identifier_byte(after)


def _identifier_byte(value: int | None) -> bool:
    return value is not None and (value >= 0x80 or value == ord("_") or chr(value).isalnum())


def _newline_offsets(source: bytes) -> tuple[int, ...]:
    return tuple(index for index, value in enumerate(source) if value == ord("\n"))


def _has_authorized_role(root, offset: int) -> bool:
    node = root.descendant_for_byte_range(offset, offset + len(_NEUTRAL_IDENTIFIER))
    if node.type != "identifier" or node.start_byte != offset or node.end_byte != offset + len(_NEUTRAL_IDENTIFIER):
        return False
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "argument" and parent.child_by_field_name("name") == node:
        return True
    field_name = next(
        (parent.field_name_for_child(index) for index, child in enumerate(parent.children) if child == node),
        None,
    )
    return field_name not in {"name", "type", "alias", "label"}
