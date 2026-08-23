"""Measure research-only HTML/XML structural candidates over pinned corpora."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from tree_sitter import Node
from tree_sitter_language_pack import get_parser


_SUFFIX_TO_FORMAT = {".html": "html", ".htm": "html", ".xml": "xml"}
_ELEMENT_TYPES = {"element", "script_element", "style_element"}


class MarkupMeasurementError(ValueError):
    """Raised when applicable markup cannot be measured authoritatively."""


@dataclass(frozen=True)
class _Element:
    tag: str
    depth: int
    start_line: int
    end_line: int
    physical_lines: int
    direct_children: int
    is_root: bool


def scan_bytes(source: bytes, format_name: str) -> dict:
    """Return source-anchored element measurements in deterministic source order."""
    if format_name not in {"html", "xml"}:
        raise ValueError(f"unsupported markup format: {format_name}")
    root = get_parser(format_name).parse(source).root_node
    errors = sum(node.is_error or node.is_missing for node in _walk(root))
    if format_name == "xml" and (root.has_error or errors):
        raise MarkupMeasurementError("XML contains a syntax error")

    elements = []
    for node in _walk(root):
        if node.type not in _ELEMENT_TYPES:
            continue
        ancestors = sum(parent.type in _ELEMENT_TYPES for parent in _parents(node))
        start_line = node.start_point.row + 1
        end_line = node.end_point.row + (1 if node.end_point.column else 0)
        end_line = max(start_line, end_line)
        elements.append(_Element(
            tag=_tag_name(node, source),
            depth=ancestors + 1,
            start_line=start_line,
            end_line=end_line,
            physical_lines=end_line - start_line + 1,
            direct_children=sum(child.type in _ELEMENT_TYPES for child in _element_children(node)),
            is_root=ancestors == 0,
        ))
    return {
        "format": format_name,
        "physicalLines": len(source.splitlines()),
        "parseHasError": root.has_error,
        "errorOrMissingNodes": errors,
        "elements": [element.__dict__ for element in elements],
    }


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _parents(node: Node):
    parent = node.parent
    while parent is not None:
        yield parent
        parent = parent.parent


def _element_children(node: Node):
    for child in node.children:
        if child.type in {"start_tag", "end_tag", "self_closing_tag", "STag", "ETag", "EmptyElemTag"}:
            continue
        if child.type in _ELEMENT_TYPES:
            yield child
        else:
            yield from _element_children(child)


def _tag_name(node: Node, source: bytes) -> str:
    for descendant in _walk(node):
        if descendant.type in {"tag_name", "Name"}:
            return source[descendant.start_byte:descendant.end_byte].decode("utf-8", "replace")
    return "?"


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
            if not any(fnmatch(relative, pattern) for pattern in specification["include"]):
                continue
            if any(fnmatch(relative, pattern) for pattern in specification.get("exclude", [])):
                continue
            try:
                row = scan_bytes(path.read_bytes(), _SUFFIX_TO_FORMAT[suffix])
                row["path"] = relative
                documents.append(row)
            except (MarkupMeasurementError, UnicodeError) as error:
                documents.append({"path": relative, "format": _SUFFIX_TO_FORMAT[suffix], "measurementError": str(error)})
        corpora.append({
            "name": specification["name"],
            "repository": specification["repository"],
            "sha": specification["sha"],
            "include": specification["include"],
            "exclude": specification.get("exclude", []),
            "summary": summarize(documents, manifest["thresholds"]),
            "documents": documents,
        })
    measured = [document for corpus in corpora for document in corpus["documents"] if "elements" in document]
    return {"thresholds": manifest["thresholds"], "summary": summarize(measured, manifest["thresholds"]), "corpora": corpora}


def summarize(documents: list[dict], thresholds: dict) -> dict:
    measured = [document for document in documents if "elements" in document]
    failed = [document for document in documents if "measurementError" in document]
    elements = [element for document in measured for element in document["elements"]]
    non_roots = [element for element in elements if not element["is_root"]]
    return {
        "documents": len(documents),
        "measuredDocuments": len(measured),
        "measurementErrors": len(failed),
        "elements": len(elements),
        "physicalLines": _distribution([document["physicalLines"] for document in measured]),
        "maxDepth": _distribution([max((e["depth"] for e in d["elements"]), default=0) for d in measured]),
        "maxNonRootSubtreeSpan": _distribution([max((e["physical_lines"] for e in d["elements"] if not e["is_root"]), default=0) for d in measured]),
        "maxFanOut": _distribution([max((e["direct_children"] for e in d["elements"]), default=0) for d in measured]),
        "depthFindings": _findings(measured, "depth", thresholds["depth"]),
        "subtreeSpanFindings": _findings(measured, "physical_lines", thresholds["subtreeSpan"], exclude_roots=True),
        "fanOutFindings": _findings(measured, "direct_children", thresholds["fanOut"]),
    }


def _findings(documents: list[dict], field: str, thresholds: list[int], *, exclude_roots: bool = False) -> dict:
    eligible = [e for d in documents for e in d["elements"] if not (exclude_roots and e["is_root"])]
    rows = {}
    for threshold in thresholds:
        per_document = [sum(e[field] > threshold and not (exclude_roots and e["is_root"]) for e in d["elements"]) for d in documents]
        count = sum(per_document)
        histogram = Counter(per_document)
        rows[str(threshold)] = {
            "findingCount": count,
            "findingPercentOfEligibleElements": _percent(count, len(eligible)),
            "affectedDocuments": sum(value > 0 for value in per_document),
            "affectedDocumentPercent": _percent(sum(value > 0 for value in per_document), len(documents)),
            "documentsWithMultipleFindings": sum(value > 1 for value in per_document),
            "findingsPerDocument": {str(value): histogram[value] for value in sorted(histogram)},
        }
    return {"eligibleElements": len(eligible), "above": rows}


def _distribution(values: list[int]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "median": None, "p75": None, "p90": None, "p95": None, "p99": None, "max": None}
    return {
        "n": len(ordered), "median": statistics.median(ordered),
        "p75": _nearest_rank(ordered, .75), "p90": _nearest_rank(ordered, .90),
        "p95": _nearest_rank(ordered, .95), "p99": _nearest_rank(ordered, .99), "max": ordered[-1],
    }


def _nearest_rank(values: list[int], percentile: float) -> int:
    return values[max(1, int(len(values) * percentile + .999999999)) - 1]


def _percent(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 2) if denominator else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = measure_manifest(args.manifest)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
