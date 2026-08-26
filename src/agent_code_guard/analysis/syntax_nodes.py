"""Shared syntax-node primitives for analyzer normalization."""


def node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")
