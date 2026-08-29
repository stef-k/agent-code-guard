"""Source/container adaptation into byte-mapped executable regions."""

from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
from pathlib import Path

from .errors import SyntaxAnalysisError
from .facts import SourcePoint, SourceRange
from .provider import ParserProvider


LANGUAGE_BY_SUFFIX = {
    ".py": "python", ".go": "go", ".kt": "kotlin", ".cs": "csharp",
    ".java": "java", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".rs": "rust", ".php": "php", ".swift": "swift", ".dart": "dart",
}
PROVIDER_LANGUAGES = (*dict.fromkeys(LANGUAGE_BY_SUFFIX.values()), "vue")
APPLICABLE_SUFFIXES = frozenset((*LANGUAGE_BY_SUFFIX, ".vue"))


@dataclass(frozen=True)
class ExecutableRegion:
    original_path: Path
    language: str
    source: bytes
    original_source: bytes
    original_byte_offset: int = 0
    original_line_starts: tuple[int, ...] | None = None
    local_line_starts: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.original_line_starts is None:
            object.__setattr__(self, "original_line_starts", _line_starts(self.original_source))
        if self.local_line_starts is None:
            object.__setattr__(self, "local_line_starts", _line_starts(self.source))

    def original_point(self, local_row: int, local_byte_column: int) -> SourcePoint:
        local_offset = self.local_line_starts[local_row] + local_byte_column
        return self.original_point_at_byte(local_offset)

    def original_point_at_byte(self, local_byte_offset: int) -> SourcePoint:
        """Map a parser byte offset without reconstructing its local row prefix."""
        absolute = self.original_byte_offset + local_byte_offset
        row = bisect_right(self.original_line_starts, absolute) - 1
        line = row + 1
        byte_column = absolute - self.original_line_starts[row] + 1
        return SourcePoint(line, byte_column, absolute)

    def original_range(self, node) -> SourceRange:
        return SourceRange(
            self.original_point_at_byte(node.start_byte),
            self.original_point_at_byte(node.end_byte),
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
        raise SyntaxAnalysisError(
            f"unable to parse {path}: Vue container syntax tree contains errors", language="vue",
        )
    regions: list[ExecutableRegion] = []
    original_line_starts = _line_starts(source)
    for element in root.named_children:
        if element.type != "script_element":
            continue
        start_tag = next(child for child in element.named_children if child.type == "start_tag")
        attributes = _attributes(start_tag, source)
        if "src" in attributes:
            raise SyntaxAnalysisError(
                f"unable to analyze {path}: external Vue script regions are unsupported", language="vue",
            )
        language = _script_language(path, attributes.get("lang"))
        raw_text = next((child for child in element.named_children if child.type == "raw_text"), None)
        if raw_text is not None:
            regions.append(ExecutableRegion(
                path, language, source[raw_text.start_byte:raw_text.end_byte], source, raw_text.start_byte,
                original_line_starts,
            ))
    return tuple(regions)


def _line_starts(source: bytes) -> tuple[int, ...]:
    return (0, *(index + 1 for index, value in enumerate(source) if value == 10))


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
    raise SyntaxAnalysisError(
        f"unable to analyze {path}: unsupported Vue script language: {value}", language="vue",
    )
