"""Measure default-threshold candidates from production analysis facts."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from agent_code_guard.analysis import analyze_files, is_applicable
from agent_code_guard.file_selection import resolve_scope
from agent_code_guard.guards.nesting import _maximum_depth
from research.complexity_sample import _Selection, _excluded, _nearest_rank


def summarize(facts, root: Path, candidates: dict[str, tuple[int, ...]]) -> dict:
    controls = defaultdict(list)
    decisions = Counter()
    for control in facts.controls:
        controls[control.callable_key].append(control)
    for decision in facts.decisions:
        decisions[decision.callable_key] += 1

    rows = []
    for callable_fact in facts.callables:
        rows.append({
            "path": callable_fact.path.resolve().relative_to(root.resolve()).as_posix(),
            "language": callable_fact.embedded_language,
            "identity": callable_fact.identity,
            "startLine": callable_fact.source_range.start_line,
            "endLine": callable_fact.source_range.end_line,
            "boundaryKind": callable_fact.boundary_kind,
            "callableSize": callable_fact.source_range.physical_loc,
            "nesting": _maximum_depth(controls[callable_fact.key])[0],
            "complexity": 1 + decisions[callable_fact.key],
        })
    rows.sort(key=lambda row: (row["language"], row["path"], row["startLine"], row["identity"]))
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["language"]].append(row)
    return {
        "supportedFiles": len(facts.files),
        "summary": {
            language: {
                metric: _metric_summary(items, metric, candidates[metric])
                for metric in ("callableSize", "nesting", "complexity")
            }
            for language, items in sorted(grouped.items())
        },
        "callables": rows,
    }


def _metric_summary(rows: list[dict], metric: str, candidates: tuple[int, ...]) -> dict:
    values = sorted(row[metric] for row in rows)
    return {
        "count": len(values),
        "values": {
            "median": statistics.median(values),
            "p75": _nearest_rank(values, 0.75),
            "p90": _nearest_rank(values, 0.90),
            "p95": _nearest_rank(values, 0.95),
            "p99": _nearest_rank(values, 0.99),
            "max": values[-1],
        },
        "candidates": {
            str(level): {
                "count": sum(value > level for value in values),
                "percent": round(100 * sum(value > level for value in values) / len(values), 2),
            }
            for level in candidates
        },
    }


def measure(paths: list[str], start: Path, excludes: tuple[str, ...], candidates: dict[str, tuple[int, ...]]) -> dict:
    scope = resolve_scope(_Selection(paths), start)
    files = tuple(path for path in scope.files if is_applicable(path) and not _excluded(path, scope.root, excludes))
    result = summarize(analyze_files(files), scope.root, candidates)
    return {"root": str(scope.root), **result}


def _candidate(value: str) -> tuple[str, int]:
    metric, separator, threshold = value.partition("=")
    if not separator or metric not in {"callableSize", "nesting", "complexity"}:
        raise argparse.ArgumentTypeError("candidate must be METRIC=POSITIVE_INTEGER")
    try:
        parsed = int(threshold)
    except ValueError as error:
        raise argparse.ArgumentTypeError("candidate must be METRIC=POSITIVE_INTEGER") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("candidate must be METRIC=POSITIVE_INTEGER")
    return metric, parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Explicit production source roots/files")
    parser.add_argument("--exclude", action="append", default=[], help="Root-relative glob to exclude")
    parser.add_argument("--candidate", action="append", type=_candidate, required=True)
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    args = parser.parse_args()
    candidates = defaultdict(list)
    for metric, threshold in args.candidate:
        candidates[metric].append(threshold)
    missing = {"callableSize", "nesting", "complexity"} - candidates.keys()
    if missing:
        parser.error("at least one candidate is required for: " + ", ".join(sorted(missing)))
    result = measure(args.paths, Path.cwd(), tuple(args.exclude), {key: tuple(value) for key, value in candidates.items()})
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
