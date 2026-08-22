"""Executable-region extraction for ordinary source files and Vue containers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node
from tree_sitter_language_pack import get_parser


LANGUAGE_BY_SUFFIX = {
    ".py": "python", ".go": "go", ".kt": "kotlin", ".cs": "csharp",
    ".java": "java", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
}


@dataclass(frozen=True)
class ExecutableRegion:
    original_path: Path
    language: str
    source: bytes
    original_source: bytes
    byte_offset: int = 0

    def original_point(self, local_row: int, local_column: int) -> tuple[int, int]:
        absolute_byte = self.byte_offset + _byte_at_point(self.source, local_row, local_column)
        prefix = self.original_source[:absolute_byte]
        row = prefix.count(b"\n")
        last_newline = prefix.rfind(b"\n")
        column = absolute_byte if last_newline < 0 else absolute_byte - last_newline - 1
        return row, column


def executable_regions(path: Path) -> list[ExecutableRegion]:
    source = path.read_bytes()
    if path.suffix.lower() == ".vue":
        return _vue_regions(path, source)
    language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
    if language is None:
        raise ValueError(f"unsupported prototype language: {path.suffix}")
    return [ExecutableRegion(path, language, source, source)]


def _vue_regions(path: Path, source: bytes) -> list[ExecutableRegion]:
    root = get_parser("vue").parse(source).root_node
    if root.has_error:
        raise ValueError(f"unable to parse {path}: container syntax tree contains errors")
    regions: list[ExecutableRegion] = []
    for element in root.named_children:
        if element.type != "script_element":
            continue
        start_tag = next(child for child in element.named_children if child.type == "start_tag")
        attributes = _attributes(start_tag, source)
        if "src" in attributes:
            raise ValueError(f"unable to analyze {path}: external Vue script regions are unsupported")
        language = _script_language(path, attributes.get("lang"))
        raw_text = next((child for child in element.named_children if child.type == "raw_text"), None)
        if raw_text is None:
            continue
        regions.append(ExecutableRegion(
            path, language, source[raw_text.start_byte:raw_text.end_byte], source, raw_text.start_byte,
        ))
    return regions


def _byte_at_point(source: bytes, row: int, column: int) -> int:
    if row == 0:
        return column
    position = 0
    for _ in range(row):
        position = source.index(b"\n", position) + 1
    return position + column


def _attributes(start_tag: Node, source: bytes) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for attribute in (child for child in start_tag.named_children if child.type == "attribute"):
        children = attribute.named_children
        name_node = next(child for child in children if child.type == "attribute_name")
        value_node = next((child for child in children if child.type == "quoted_attribute_value"), None)
        name = source[name_node.start_byte:name_node.end_byte].decode("utf-8").lower()
        value = None
        if value_node is not None:
            value = source[value_node.start_byte:value_node.end_byte].decode("utf-8")[1:-1].lower()
        values[name] = value
    return values


def _script_language(path: Path, value: str | None) -> str:
    if value in {None, "js", "javascript"}:
        return "javascript"
    if value in {"ts", "typescript"}:
        return "typescript"
    raise ValueError(f"unable to analyze {path}: unsupported Vue script language: {value}")
