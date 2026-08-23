"""Measure research-only Markdown document and heading-delimited section size."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path


_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?)|[ \t]*)$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_MARKDOWN_SUFFIXES = {".md", ".markdown"}


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


def scan_text(text: str) -> dict:
    """Return deterministic bounded Markdown structure and physical spans."""
    lines = text.splitlines()
    headings, fenced_lines, unclosed = _scan_structure(lines)
    return {
        "totalPhysicalLines": len(lines),
        "nonblankPhysicalLines": sum(bool(line.strip()) for line in lines),
        "nonblankLinesExcludingFencedCode": sum(
            bool(line.strip()) and number not in fenced_lines
            for number, line in enumerate(lines, 1)
        ),
        "preambleLines": headings[0].start_line - 1 if headings else len(lines),
        "maxHeadingDepth": max((heading.level for heading in headings), default=0),
        "unclosedFence": unclosed,
        "headings": [_heading_row(heading) for heading in headings],
        "directContentSections": _section_rows(headings, lines, fenced_lines, subtree=False),
        "subtreeSections": _section_rows(headings, lines, fenced_lines, subtree=True),
    }


def _scan_structure(lines: list[str]) -> tuple[list[_Heading], set[int], bool]:
    headings: list[_Heading] = []
    fenced_lines: set[int] = set()
    fence: _Fence | None = None
    for index, line in enumerate(lines):
        line_number = index + 1
        if fence:
            fenced_lines.add(line_number)
            if _closes_fence(line, fence):
                fence = None
            continue
        opened = _opens_fence(line)
        if opened:
            fence = opened
            fenced_lines.add(line_number)
            continue
        atx = _atx_heading(line, line_number)
        if atx:
            headings.append(atx)
            continue
        setext = _setext_heading(lines, index)
        if setext and (not headings or headings[-1].end_line != line_number - 1):
            headings.append(setext)
    return headings, fenced_lines, fence is not None


def _opens_fence(line: str) -> _Fence | None:
    match = _FENCE_OPEN.match(line)
    if not match:
        return None
    run, info = match.groups()
    if run[0] == "`" and "`" in info:
        return None
    return _Fence(run[0], len(run))


def _closes_fence(line: str, fence: _Fence) -> bool:
    return bool(re.match(
        rf"^ {{0,3}}{re.escape(fence.marker)}{{{fence.length},}}[ \t]*$",
        line,
    ))


def _atx_heading(line: str, line_number: int) -> _Heading | None:
    match = _ATX.match(line)
    if not match:
        return None
    hashes, raw_text = match.groups()
    text = raw_text or ""
    text = re.sub(r"[ \t]+#+[ \t]*$", "", text).strip()
    return _Heading(text, len(hashes), line_number, line_number)


def _setext_heading(lines: list[str], index: int) -> _Heading | None:
    if index == 0 or not _SETEXT.match(lines[index]):
        return None
    title = lines[index - 1]
    if not title.strip() or len(title) - len(title.lstrip(" ")) >= 4:
        return None
    if _ATX.match(title) or _FENCE_OPEN.match(title):
        return None
    underline = _SETEXT.match(lines[index]).group(1)
    return _Heading(title.strip(), 1 if underline[0] == "=" else 2, index, index + 1)


def _heading_row(heading: _Heading) -> dict:
    return {
        "text": heading.text,
        "level": heading.level,
        "startLine": heading.start_line,
        "endLine": heading.end_line,
    }


def _section_rows(
    headings: list[_Heading], lines: list[str], fenced_lines: set[int], *, subtree: bool,
) -> list[dict]:
    rows = []
    for index, heading in enumerate(headings):
        following = headings[index + 1:]
        if subtree:
            following = [item for item in following if item.level <= heading.level]
        end_line = following[0].start_line - 1 if following else len(lines)
        span = range(heading.start_line, end_line + 1)
        rows.append({
            "heading": heading.text,
            "level": heading.level,
            "startLine": heading.start_line,
            "endLine": end_line,
            "physicalLines": end_line - heading.start_line + 1,
            "nonblankLines": sum(bool(lines[number - 1].strip()) for number in span),
            "physicalLinesExcludingFencedCode": sum(number not in fenced_lines for number in span),
        })
    return rows


def measure(
    paths: list[str], start: Path, excludes: tuple[str, ...] = (),
    document_thresholds: tuple[int, ...] = (300, 500, 800, 1200),
    section_thresholds: tuple[int, ...] = (100, 150, 200, 300),
) -> dict:
    """Scan explicit Markdown paths and return stable rows and distributions."""
    root = start.resolve()
    files = _select_files(paths, root, excludes)
    documents = []
    for path in files:
        row = scan_text(path.read_text(encoding="utf-8"))
        row["path"] = path.relative_to(root).as_posix()
        documents.append(row)
    return {
        "root": str(root),
        "suffixes": sorted(_MARKDOWN_SUFFIXES),
        "excludes": sorted(set(excludes)),
        "summary": _summaries(documents, document_thresholds, section_thresholds),
        "documents": documents,
    }


def _select_files(paths: list[str], root: Path, excludes: tuple[str, ...]) -> list[Path]:
    selected: set[Path] = set()
    for supplied in paths:
        path = Path(supplied).resolve()
        candidates = path.rglob("*") if path.is_dir() else (path,)
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in _MARKDOWN_SUFFIXES:
                continue
            relative = candidate.relative_to(root).as_posix()
            if not any(fnmatch(relative, pattern) for pattern in excludes):
                selected.add(candidate)
    return sorted(selected, key=lambda path: path.relative_to(root).as_posix())


def _summaries(documents: list[dict], doc_thresholds: tuple[int, ...], section_thresholds: tuple[int, ...]) -> dict:
    direct = [max((s["physicalLines"] for s in row["directContentSections"]), default=0) for row in documents]
    subtree = [max((s["physicalLines"] for s in row["subtreeSections"]), default=0) for row in documents]
    return {
        "documents": len(documents),
        "totalPhysicalLines": _distribution([row["totalPhysicalLines"] for row in documents], doc_thresholds),
        "nonblankPhysicalLines": _distribution([row["nonblankPhysicalLines"] for row in documents], doc_thresholds),
        "maxDirectContentSectionLines": _distribution(direct, section_thresholds),
        "maxSubtreeSectionLines": _distribution(subtree, section_thresholds),
        "maxHeadingDepth": _distribution([row["maxHeadingDepth"] for row in documents], (3, 4, 5, 6)),
    }


def _distribution(values: list[int], thresholds: tuple[int, ...]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "median": None, "p75": None, "p90": None, "p95": None, "p99": None,
                "max": None, "above": {}}
    return {
        "n": len(ordered),
        "median": statistics.median(ordered),
        "p75": _nearest_rank(ordered, 0.75),
        "p90": _nearest_rank(ordered, 0.90),
        "p95": _nearest_rank(ordered, 0.95),
        "p99": _nearest_rank(ordered, 0.99),
        "max": ordered[-1],
        "above": {
            str(level): {
                "count": sum(value > level for value in ordered),
                "percent": round(100 * sum(value > level for value in ordered) / len(ordered), 2),
            }
            for level in thresholds
        },
    }


def _nearest_rank(values: list[int], percentile: float) -> int:
    rank = max(1, int(len(values) * percentile + 0.999999999))
    return values[rank - 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Explicit Markdown files/directories")
    parser.add_argument("--exclude", action="append", default=[], help="Root-relative glob")
    parser.add_argument("--document-threshold", action="append", type=int)
    parser.add_argument("--section-threshold", action="append", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = measure(
        args.paths, Path.cwd(), tuple(args.exclude),
        tuple(args.document_threshold or (300, 500, 800, 1200)),
        tuple(args.section_threshold or (100, 150, 200, 300)),
    )
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
