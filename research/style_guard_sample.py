"""Measure research-only CSS/SCSS maintainability candidates over pinned corpora."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path

_SUFFIX_TO_FORMAT = {".css": "css", ".scss": "scss"}
_CONTROL_NAMES = frozenset({"if", "else", "for", "each", "while"})
_AT_RULE_NAMES = frozenset(
    {
        "container",
        "document",
        "layer",
        "media",
        "scope",
        "starting-style",
        "supports",
    }
)
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"//[^\r\n]*")
_IDENTIFIER = re.compile(r"(?<![-\w#.$%])(?:--)?[a-zA-Z_][\w-]*")


def scan_bytes(source: bytes, format_name: str) -> dict:
    """Return deterministic source-ranged style facts in authored order.

    This deliberately small research scanner recognizes balanced braces after
    removing comments, strings, and Sass interpolation from brace semantics.
    It recovers unmatched structure to EOF and reports recovery telemetry; it
    does not decide whether the stylesheet is valid.
    """
    if format_name not in {"css", "scss"}:
        raise ValueError(f"unsupported style format: {format_name}")
    text = source.decode("utf-8")
    physical_lines = len(text.splitlines())
    blocks: list[dict] = []
    selectors: list[dict] = []
    stack: list[dict] = []
    boundaries = [0]
    errors = 0
    line = 1
    index = 0
    quote: str | None = None
    comment = False
    line_comment = False
    interpolation_depth = 0

    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if char == "\n":
            line += 1
            line_comment = False
        if line_comment:
            index += 1
            continue
        if comment:
            if char == "*" and following == "/":
                comment = False
                index += 2
                continue
            index += 1
            continue
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char == "/" and following == "*":
            comment = True
            index += 2
            continue
        if format_name == "scss" and char == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if format_name == "scss" and char == "#" and following == "{":
            interpolation_depth += 1
            index += 2
            continue
        if interpolation_depth:
            if char == "{":
                interpolation_depth += 1
            elif char == "}":
                interpolation_depth -= 1
            index += 1
            continue
        if char == "{":
            _open_block(text, format_name, index, line, boundaries, stack, blocks, selectors)
        elif char == ";":
            _count_declaration(text, boundaries[-1], index, stack)
            boundaries[-1] = index + 1
        elif char == "}":
            if not stack:
                errors += 1
                boundaries[-1] = index + 1
            else:
                _close_block(text, index, line, boundaries, stack)
        index += 1

    for block in stack:
        block["end_line"] = max(block["start_line"], physical_lines)
        block["physical_lines"] = block["end_line"] - block["start_line"] + 1
        block["recovered"] = True
    errors += len(stack) + int(comment or quote is not None or interpolation_depth > 0)
    return {
        "format": format_name,
        "physicalLines": physical_lines,
        "parseHasError": errors > 0,
        "recoveredBlocks": len(stack),
        "errorCount": errors,
        "blocks": blocks,
        "selectors": selectors,
    }


def _open_block(
    text: str,
    format_name: str,
    index: int,
    line: int,
    boundaries: list[int],
    stack: list[dict],
    blocks: list[dict],
    selectors: list[dict],
) -> None:
    header = _clean_header(text[boundaries[-1] : index])
    kind = _classify(header, stack)
    selector_depth = sum(item["kind"] == "rule" for item in stack)
    at_rule_depth = sum(item["kind"] == "at-rule" for item in stack)
    control_depth = sum(item["kind"] == "control" for item in stack)
    selector_depth += kind == "rule"
    at_rule_depth += kind == "at-rule"
    control_depth += kind == "control"
    block = {
        "kind": kind,
        "header": " ".join(header.split())[:240],
        "start_line": _line_at(text, format_name, boundaries[-1], index),
        "end_line": line,
        "physical_lines": 1,
        "declarations": 0,
        "custom_property_declarations": 0,
        "selector_depth": selector_depth,
        "at_rule_depth": at_rule_depth,
        "control_depth": control_depth,
        "has_parent_selector": kind == "rule" and "&" in header,
        "recovered": False,
    }
    blocks.append(block)
    if kind == "rule":
        selectors.append(_selector_fact(header, block))
    stack.append(block)
    boundaries[-1] = index + 1
    boundaries.append(index + 1)


def _count_declaration(text: str, start: int, end: int, stack: list[dict]) -> None:
    if not stack:
        return
    statement = _clean_header(text[start:end])
    if not _is_declaration(statement):
        return
    stack[-1]["declarations"] += 1
    if statement.lstrip().startswith("--"):
        stack[-1]["custom_property_declarations"] += 1


def _close_block(
    text: str,
    index: int,
    line: int,
    boundaries: list[int],
    stack: list[dict],
) -> None:
    _count_declaration(text, boundaries[-1], index, stack)
    block = stack.pop()
    block["end_line"] = line
    block["physical_lines"] = line - block["start_line"] + 1
    boundaries.pop()
    boundaries[-1] = index + 1


def _line_at(text: str, format_name: str, start: int, end: int) -> int:
    meaningful = start
    while meaningful < end:
        if text.startswith("/*", meaningful):
            close = text.find("*/", meaningful + 2)
            meaningful = end if close < 0 else close + 2
        elif format_name == "scss" and text.startswith("//", meaningful):
            newline = text.find("\n", meaningful + 2)
            meaningful = end if newline < 0 else newline + 1
        elif text[meaningful].isspace():
            meaningful += 1
        else:
            break
    return text.count("\n", 0, meaningful) + 1


def _clean_header(value: str) -> str:
    return _LINE_COMMENT.sub(" ", _COMMENT.sub(" ", value)).strip()


def _classify(header: str, stack: list[dict]) -> str:
    lowered = header.lower()
    name_match = re.match(r"@(?:-[\w]+-)?([\w-]+)", lowered)
    name = name_match.group(1) if name_match else ""
    if name in {"keyframes"}:
        return "keyframes"
    if stack and stack[-1]["kind"] == "keyframes":
        return "keyframe-step"
    if name == "mixin":
        return "mixin"
    if name == "function":
        return "function"
    if name in _CONTROL_NAMES:
        return "control"
    if name in _AT_RULE_NAMES or header.startswith("@"):
        return "at-rule"
    return "rule"


def _is_declaration(statement: str) -> bool:
    return bool(statement and not statement.startswith("@") and ":" in statement)


def _selector_fact(header: str, block: dict) -> dict:
    parts = _split_selectors(header)
    measurements = [_measure_selector(part) for part in parts]
    return {
        "header": block["header"],
        "start_line": block["start_line"],
        "selector_depth": block["selector_depth"],
        "has_parent_selector": block["has_parent_selector"],
        "selector_count": len(parts),
        "max_components": max((item[0] for item in measurements), default=0),
        "max_combinators": max((item[1] for item in measurements), default=0),
        "max_specificity": max((item[2] for item in measurements), default=0),
    }


def _split_selectors(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(value):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def _measure_selector(value: str) -> tuple[int, int, int]:
    scrubbed = re.sub(r"#\{.*?\}", "x", value)
    ids = len(re.findall(r"#[\w-]+", scrubbed))
    classes = len(re.findall(r"\.[\w-]+|\[[^]]+\]|:(?!:)[\w-]+", scrubbed))
    pseudo_elements = len(re.findall(r"::[\w-]+", scrubbed))
    combinators = len(re.findall(r"\s*[>+~]\s*|\s+", scrubbed.strip()))
    identifiers = [
        item
        for item in _IDENTIFIER.findall(scrubbed)
        if item.lower() not in {"not", "is", "where", "has"}
    ]
    type_count = max(0, len(identifiers) - ids - classes - pseudo_elements)
    components = ids + classes + pseudo_elements + type_count
    specificity = ids * 100 + classes * 10 + pseudo_elements + type_count
    return components, combinators, specificity


def measure_manifest(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpora = []
    for specification in manifest["corpora"]:
        root = Path(specification["root"]).resolve()
        documents = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _SUFFIX_TO_FORMAT:
                continue
            relative = path.relative_to(root).as_posix()
            if not any(fnmatch(relative, pattern) for pattern in specification["include"]):
                continue
            if any(fnmatch(relative, pattern) for pattern in specification.get("exclude", [])):
                continue
            try:
                row = scan_bytes(path.read_bytes(), _SUFFIX_TO_FORMAT[path.suffix.lower()])
                row["path"] = relative
                documents.append(row)
            except UnicodeError as error:
                documents.append({"path": relative, "measurementError": str(error)})
        corpora.append(
            {
                **{key: value for key, value in specification.items() if key != "root"},
                "summary": summarize(documents, manifest["thresholds"]),
                "documents": documents,
            }
        )
    measured = [document for corpus in corpora for document in corpus["documents"] if "blocks" in document]
    return {"thresholds": manifest["thresholds"], "summary": summarize(measured, manifest["thresholds"]), "corpora": corpora}


def summarize(documents: list[dict], thresholds: dict) -> dict:
    measured = [document for document in documents if "blocks" in document]
    blocks = [block for document in measured for block in document["blocks"]]
    rules = [block for block in blocks if block["kind"] == "rule"]
    scss_rules = [block for document in measured if document["format"] == "scss" for block in document["blocks"] if block["kind"] == "rule"]
    selectors = [selector for document in measured for selector in document["selectors"]]
    return {
        "documents": len(documents),
        "measuredDocuments": len(measured),
        "measurementErrors": len(documents) - len(measured),
        "recoveredDocuments": sum(document["parseHasError"] for document in measured),
        "blocks": len(blocks),
        "rules": len(rules),
        "scssRules": len(scss_rules),
        "selectors": len(selectors),
        "blockPhysicalLines": _distribution([block["physical_lines"] for block in blocks]),
        "scssSelectorDepth": _distribution([block["selector_depth"] for block in scss_rules]),
        "selectorComponents": _distribution([selector["max_components"] for selector in selectors]),
        "selectorCombinators": _distribution([selector["max_combinators"] for selector in selectors]),
        "selectorSpecificity": _distribution([selector["max_specificity"] for selector in selectors]),
        "declarationsPerBlock": _distribution([block["declarations"] for block in blocks]),
        "blockSizeFindings": _findings(measured, lambda d: d["blocks"], "physical_lines", thresholds["blockSize"]),
        "selectorDepthFindings": _findings([d for d in measured if d["format"] == "scss"], lambda d: [b for b in d["blocks"] if b["kind"] == "rule"], "selector_depth", thresholds["selectorDepth"]),
        "selectorComponentFindings": _findings(measured, lambda d: d["selectors"], "max_components", thresholds["selectorComponents"]),
        "declarationFindings": _findings(measured, lambda d: d["blocks"], "declarations", thresholds["declarations"]),
    }


def _findings(documents: list[dict], items, field: str, thresholds: list[int]) -> dict:
    eligible = [item for document in documents for item in items(document)]
    rows = {}
    for threshold in thresholds:
        per_document = [sum(item[field] > threshold for item in items(document)) for document in documents]
        count = sum(per_document)
        histogram = Counter(per_document)
        affected = sum(value > 0 for value in per_document)
        rows[str(threshold)] = {
            "findingCount": count,
            "findingPercentOfEligibleNodes": _percent(count, len(eligible)),
            "affectedDocuments": affected,
            "affectedDocumentPercent": _percent(affected, len(documents)),
            "documentsWithMultipleFindings": sum(value > 1 for value in per_document),
            "findingsPerDocument": {str(value): histogram[value] for value in sorted(histogram)},
        }
    return {"eligibleNodes": len(eligible), "above": rows}


def _distribution(values: list[int]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "median": None, "p75": None, "p90": None, "p95": None, "p99": None, "max": None}
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
    rendered = json.dumps(measure_manifest(args.manifest), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
