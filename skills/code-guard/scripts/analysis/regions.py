"""Source/container adaptation into byte-mapped executable regions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import SyntaxAnalysisError
from .facts import SourcePoint, SourceRange
from .provider import ParserProvider


LANGUAGE_BY_SUFFIX = {
    ".py": "python", ".go": "go", ".kt": "kotlin", ".cs": "csharp",
    ".java": "java", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
}
APPLICABLE_SUFFIXES = frozenset((*LANGUAGE_BY_SUFFIX, ".vue"))


@dataclass(frozen=True)
class ExecutableRegion:
    original_path: Path
    language: str
    source: bytes
    original_source: bytes
    original_byte_offset: int = 0

    def original_point(self, local_row: int, local_byte_column: int) -> SourcePoint:
        absolute = self.original_byte_offset + _byte_at_point(self.source, local_row, local_byte_column)
        prefix = self.original_source[:absolute]
        line = prefix.count(b"\n") + 1
        newline = prefix.rfind(b"\n")
        byte_column = absolute + 1 if newline < 0 else absolute - newline
        return SourcePoint(line, byte_column, absolute)

    def original_range(self, node) -> SourceRange:
        return SourceRange(
            self.original_point(node.start_point.row, node.start_point.column),
            self.original_point(node.end_point.row, node.end_point.column),
        )


def is_applicable(path: Path) -> bool:
    return path.suffix.lower() in APPLICABLE_SUFFIXES


def executable_regions(path: Path, provider: ParserProvider) -> tuple[ExecutableRegion, ...]:
    source = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".vue":
        return _vue_regions(path, source, provider)
    language = LANGUAGE_BY_SUFFIX.get(suffix)
    if language is None:
        return ()
    return (ExecutableRegion(path, language, source, source),)


def _vue_regions(path: Path, source: bytes, provider: ParserProvider) -> tuple[ExecutableRegion, ...]:
    root = provider.parse("vue", source).root_node
    if root.has_error:
        raise SyntaxAnalysisError(f"unable to parse {path}: Vue container syntax tree contains errors")
    regions: list[ExecutableRegion] = []
    for element in root.named_children:
        if element.type != "script_element":
            continue
        start_tag = next(child for child in element.named_children if child.type == "start_tag")
        attributes = _attributes(start_tag, source)
        if "src" in attributes:
            raise SyntaxAnalysisError(f"unable to analyze {path}: external Vue script regions are unsupported")
        language = _script_language(path, attributes.get("lang"))
        raw_text = next((child for child in element.named_children if child.type == "raw_text"), None)
        if raw_text is not None:
            regions.append(ExecutableRegion(
                path, language, source[raw_text.start_byte:raw_text.end_byte], source, raw_text.start_byte,
            ))
    return tuple(regions)


def _byte_at_point(source: bytes, row: int, column: int) -> int:
    position = 0
    for _ in range(row):
        position = source.index(b"\n", position) + 1
    return position + column


def _attributes(start_tag, source: bytes) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for attribute in (child for child in start_tag.named_children if child.type == "attribute"):
        name_node = next(child for child in attribute.named_children if child.type == "attribute_name")
        value_node = next((child for child in attribute.named_children if child.type == "quoted_attribute_value"), None)
        name = source[name_node.start_byte:name_node.end_byte].decode("utf-8").lower()
        value = None if value_node is None else source[value_node.start_byte:value_node.end_byte].decode("utf-8")[1:-1].lower()
        values[name] = value
    return values


def _script_language(path: Path, value: str | None) -> str:
    if value in {None, "js", "javascript"}:
        return "javascript"
    if value in {"ts", "typescript"}:
        return "typescript"
    raise SyntaxAnalysisError(f"unable to analyze {path}: unsupported Vue script language: {value}")
