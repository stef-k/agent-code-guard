"""Measure research-only HTML/XML structural candidates over pinned corpora."""

from __future__ import annotations

import argparse, json, statistics
from collections import Counter
from fnmatch import fnmatch
from html.parser import HTMLParser
from pathlib import Path
from xml.parsers import expat

_SUFFIX_TO_FORMAT = {".html": "html", ".htm": "html", ".xml": "xml"}
_VOID_HTML = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


class MarkupMeasurementError(ValueError):
    """Raised when applicable markup cannot be measured authoritatively."""


class _ElementEvents:
    def __init__(self, physical_lines: int) -> None:
        self.physical_lines = physical_lines
        self.elements: list[dict] = []
        self.stack: list[int] = []
        self.recoveries = 0

    def start(self, tag: str, line: int, *, empty: bool = False) -> None:
        if self.stack:
            self.elements[self.stack[-1]]["direct_children"] += 1
        index = len(self.elements)
        self.elements.append(
            {
                "tag": tag,
                "depth": len(self.stack) + 1,
                "start_line": line,
                "end_line": line,
                "physical_lines": 1,
                "direct_children": 0,
                "is_root": not self.stack,
            }
        )
        if not empty:
            self.stack.append(index)

    def end(self, tag: str, line: int, *, tolerant: bool) -> None:
        match = next(
            (
                offset
                for offset in range(len(self.stack) - 1, -1, -1)
                if self.elements[self.stack[offset]]["tag"] == tag
            ),
            None,
        )
        if match is None:
            if tolerant:
                self.recoveries += 1
                return
            raise MarkupMeasurementError(f"unexpected XML end tag: {tag}")
        if tolerant:
            self.recoveries += len(self.stack) - match - 1
        for index in self.stack[match:]:
            element = self.elements[index]
            element["end_line"] = line
            element["physical_lines"] = line - element["start_line"] + 1
        del self.stack[match:]

    def finish(self, *, tolerant: bool) -> list[dict]:
        if self.stack and not tolerant:
            raise MarkupMeasurementError("unclosed XML element")
        if tolerant:
            self.recoveries += len(self.stack)
            for index in self.stack:
                element = self.elements[index]
                element["end_line"] = max(element["start_line"], self.physical_lines)
                element["physical_lines"] = (
                    element["end_line"] - element["start_line"] + 1
                )
        self.stack.clear()
        return self.elements


class _AuthoredHtmlParser(HTMLParser):
    def __init__(self, physical_lines: int) -> None:
        super().__init__(convert_charrefs=False)
        self.events = _ElementEvents(physical_lines)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.events.start(tag, self.getpos()[0], empty=tag in _VOID_HTML)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.events.start(tag, self.getpos()[0], empty=True)

    def handle_endtag(self, tag: str) -> None:
        self.events.end(tag, self.getpos()[0], tolerant=True)


def scan_bytes(source: bytes, format_name: str) -> dict:
    """Return source-anchored element measurements in deterministic source order."""
    if format_name not in {"html", "xml"}:
        raise ValueError(f"unsupported markup format: {format_name}")
    text = source.decode("utf-8")
    physical_lines = len(text.splitlines())
    events = _ElementEvents(physical_lines)
    if format_name == "html":
        parser = _AuthoredHtmlParser(physical_lines)
        parser.feed(text)
        parser.close()
        events = parser.events
        elements = events.finish(tolerant=True)
    else:
        parser = expat.ParserCreate()
        parser.StartElementHandler = lambda tag, attrs: events.start(
            tag, parser.CurrentLineNumber
        )
        parser.EndElementHandler = lambda tag: events.end(
            tag, parser.CurrentLineNumber, tolerant=False
        )
        try:
            parser.Parse(source, True)
        except expat.ExpatError as error:
            raise MarkupMeasurementError(
                f"XML syntax error at {error.lineno}:{error.offset}: {expat.ErrorString(error.code)}"
            ) from error
        elements = events.finish(tolerant=False)
    return {
        "format": format_name,
        "physicalLines": physical_lines,
        "parseHasError": False,
        "errorOrMissingNodes": events.recoveries,
        "elements": elements,
    }


def measure_manifest(manifest_path: Path) -> dict:
    """Measure explicit pinned corpus roots described by a JSON manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpora = []
    for specification in manifest["corpora"]:
        root = Path(specification["root"]).resolve()
        documents = []
        for path in sorted(root.rglob("*")):
            suffix = path.suffix.lower()
            if not path.is_file() or suffix not in _SUFFIX_TO_FORMAT:
                continue
            relative = path.relative_to(root).as_posix()
            if not any(
                fnmatch(relative, pattern) for pattern in specification["include"]
            ):
                continue
            if any(
                fnmatch(relative, pattern)
                for pattern in specification.get("exclude", [])
            ):
                continue
            try:
                row = scan_bytes(path.read_bytes(), _SUFFIX_TO_FORMAT[suffix])
                row["path"] = relative
                documents.append(row)
            except (MarkupMeasurementError, UnicodeError) as error:
                documents.append(
                    {
                        "path": relative,
                        "format": _SUFFIX_TO_FORMAT[suffix],
                        "measurementError": str(error),
                    }
                )
        corpora.append(
            {
                "name": specification["name"],
                "repository": specification["repository"],
                "sha": specification["sha"],
                "include": specification["include"],
                "exclude": specification.get("exclude", []),
                "summary": summarize(documents, manifest["thresholds"]),
                "documents": documents,
            }
        )
    measured = [d for corpus in corpora for d in corpus["documents"] if "elements" in d]
    return {
        "thresholds": manifest["thresholds"],
        "summary": summarize(measured, manifest["thresholds"]),
        "corpora": corpora,
    }


def summarize(documents: list[dict], thresholds: dict) -> dict:
    measured = [d for d in documents if "elements" in d]
    failed = [d for d in documents if "measurementError" in d]
    elements = [e for d in measured for e in d["elements"]]
    return {
        "documents": len(documents),
        "measuredDocuments": len(measured),
        "measurementErrors": len(failed),
        "elements": len(elements),
        "htmlRecoveryDocuments": sum(
            d["format"] == "html" and d["errorOrMissingNodes"] > 0 for d in measured
        ),
        "physicalLines": _distribution([d["physicalLines"] for d in measured]),
        "maxDepth": _distribution(
            [max((e["depth"] for e in d["elements"]), default=0) for d in measured]
        ),
        "maxNonRootSubtreeSpan": _distribution(
            [
                max(
                    (e["physical_lines"] for e in d["elements"] if not e["is_root"]),
                    default=0,
                )
                for d in measured
            ]
        ),
        "maxFanOut": _distribution(
            [
                max((e["direct_children"] for e in d["elements"]), default=0)
                for d in measured
            ]
        ),
        "depthFindings": _findings(measured, "depth", thresholds["depth"]),
        "subtreeSpanFindings": _findings(
            measured, "physical_lines", thresholds["subtreeSpan"], exclude_roots=True
        ),
        "fanOutFindings": _findings(measured, "direct_children", thresholds["fanOut"]),
    }


def _findings(
    documents: list[dict],
    field: str,
    thresholds: list[int],
    *,
    exclude_roots: bool = False,
) -> dict:
    eligible = [
        e
        for d in documents
        for e in d["elements"]
        if not (exclude_roots and e["is_root"])
    ]
    rows = {}
    for threshold in thresholds:
        per_document = [
            sum(
                e[field] > threshold and not (exclude_roots and e["is_root"])
                for e in d["elements"]
            )
            for d in documents
        ]
        count = sum(per_document)
        histogram = Counter(per_document)
        affected = sum(value > 0 for value in per_document)
        rows[str(threshold)] = {
            "findingCount": count,
            "findingPercentOfEligibleElements": _percent(count, len(eligible)),
            "affectedDocuments": affected,
            "affectedDocumentPercent": _percent(affected, len(documents)),
            "documentsWithMultipleFindings": sum(value > 1 for value in per_document),
            "findingsPerDocument": {
                str(value): histogram[value] for value in sorted(histogram)
            },
        }
    return {"eligibleElements": len(eligible), "above": rows}


def _distribution(values: list[int]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {
            "n": 0,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    return {
        "n": len(ordered),
        "median": statistics.median(ordered),
        "p75": _nearest_rank(ordered, 0.75),
        "p90": _nearest_rank(ordered, 0.90),
        "p95": _nearest_rank(ordered, 0.95),
        "p99": _nearest_rank(ordered, 0.99),
        "max": ordered[-1],
    }


def _nearest_rank(values: list[int], percentile: float) -> int:
    return values[max(1, int(len(values) * percentile + 0.999999999)) - 1]


def _percent(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 2) if denominator else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = (
        json.dumps(measure_manifest(args.manifest), indent=2, ensure_ascii=False) + "\n"
    )
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
