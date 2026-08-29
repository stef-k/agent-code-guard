"""Bounded CommonMark-informed scanner for admitted Markdown size facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..invocation import SelectedFile

from .facts import MarkdownDocumentFact, MarkdownFacts, MarkdownSectionFact

_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?)|[ \t]*)$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_BLOCK_PREFIX = re.compile(r"^ {0,3}(?:>|[-+*][ \t]+|\d{1,9}[.)][ \t]+|<)")


@dataclass(frozen=True)
class _Heading:
    text: str
    level: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class _Fence:
    marker: str
    length: int


def analyze_files(files: tuple[SelectedFile, ...] | tuple[Path, ...] | list[Path]) -> MarkdownFacts:
    identities = tuple(
        (value, value.reporting_path) if isinstance(value, SelectedFile)
        else (SelectedFile(value.as_posix(), value), None)
        for value in files
    )
    applicable = sorted(
        ((selected, report) for selected, report in identities if selected.physical_path.suffix.lower() == ".md"),
        key=lambda item: item[0].physical_path.as_posix(),
    )
    return MarkdownFacts(tuple(
        scan_text(
            selected.physical_path,
            selected.physical_path.read_text(encoding="utf-8"),
            report,
        )
        for selected, report in applicable
    ))


def scan_text(path: Path, text: str, reporting_path: str | None = None) -> MarkdownDocumentFact:
    lines = text.splitlines()
    headings = _scan_headings(lines)
    sections = []
    for index, heading in enumerate(headings):
        end_line = headings[index + 1].start_line - 1 if index + 1 < len(headings) else len(lines)
        sections.append(MarkdownSectionFact(
            heading.text, heading.level, heading.start_line, end_line,
            end_line - heading.start_line + 1,
        ))
    return MarkdownDocumentFact(path, len(lines), tuple(sections), reporting_path)


def _scan_headings(lines: list[str]) -> list[_Heading]:
    headings: list[_Heading] = []
    fence: _Fence | None = None
    for index, line in enumerate(lines):
        line_number = index + 1
        if fence:
            if _closes_fence(line, fence):
                fence = None
            continue
        opened = _opens_fence(line)
        if opened:
            fence = opened
            continue
        atx = _atx_heading(line, line_number)
        if atx:
            headings.append(atx)
            continue
        setext = _setext_heading(lines, index)
        if setext and (not headings or headings[-1].end_line != line_number - 1):
            headings.append(setext)
    return headings


def _opens_fence(line: str) -> _Fence | None:
    match = _FENCE_OPEN.match(line)
    if not match:
        return None
    run, info = match.groups()
    if run[0] == "`" and "`" in info:
        return None
    return _Fence(run[0], len(run))


def _closes_fence(line: str, fence: _Fence) -> bool:
    return bool(re.match(rf"^ {{0,3}}{re.escape(fence.marker)}{{{fence.length},}}[ \t]*$", line))


def _atx_heading(line: str, line_number: int) -> _Heading | None:
    match = _ATX.match(line)
    if not match:
        return None
    hashes, raw_text = match.groups()
    text = re.sub(r"[ \t]+#+[ \t]*$", "", raw_text or "").strip()
    return _Heading(text, len(hashes), line_number, line_number)


def _setext_heading(lines: list[str], index: int) -> _Heading | None:
    match = _SETEXT.match(lines[index]) if index else None
    if not match:
        return None
    title = lines[index - 1]
    if index >= 2 and lines[index - 2].strip():
        return None
    if not title.strip() or len(title) - len(title.lstrip(" ")) >= 4:
        return None
    if _ATX.match(title) or _FENCE_OPEN.match(title) or _BLOCK_PREFIX.match(title):
        return None
    return _Heading(title.strip(), 1 if match.group(1)[0] == "=" else 2, index, index + 1)
