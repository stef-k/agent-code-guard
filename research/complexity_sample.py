"""Measure research-only cyclomatic complexity from production analysis facts."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from agent_code_guard.analysis import analyze_files, is_applicable
from agent_code_guard.file_selection import resolve_scope
from agent_code_guard.invocation import SelectedFile


@dataclass(frozen=True)
class _Selection:
    paths: list[str]
    changed_only: bool = False
    staged: bool = False
    base_ref: str | None = None


def measure(
    paths: list[str],
    start: Path,
    excludes: tuple[str, ...] = (),
    excluded_decisions: tuple[str, ...] = (),
) -> dict:
    """Resolve explicit scope and aggregate existing production facts."""
    scope = resolve_scope(_Selection(paths), start)
    files = tuple(path for path in scope.files if is_applicable(path) and not _excluded(path, scope.root, excludes))
    facts = analyze_files(tuple(
        SelectedFile(path.relative_to(scope.root).as_posix(), path) for path in files
    ))
    decisions = defaultdict(Counter)
    for decision in facts.decisions:
        if decision.category in excluded_decisions:
            continue
        decisions[decision.callable_key][decision.category] += 1

    rows = []
    for callable_fact in facts.callables:
        breakdown = decisions[callable_fact.key]
        rows.append({
            "path": callable_fact.path.resolve().relative_to(scope.root).as_posix(),
            "language": callable_fact.embedded_language,
            "identity": callable_fact.identity,
            "startLine": callable_fact.source_range.start_line,
            "endLine": callable_fact.source_range.end_line,
            "boundaryKind": callable_fact.boundary_kind,
            "complexity": 1 + sum(breakdown.values()),
            "decisions": dict(sorted(breakdown.items())),
        })
    rows.sort(key=lambda row: (row["language"], row["path"], row["startLine"], row["identity"]))
    return {
        "root": str(scope.root),
        "supportedFiles": len(facts.files),
        "parseFailures": 0,
        "excludedDecisions": sorted(set(excluded_decisions)),
        "summary": _summaries(rows),
        "callables": rows,
    }


def _excluded(path: Path, root: Path, patterns: tuple[str, ...]) -> bool:
    relative = path.resolve().relative_to(root).as_posix()
    return any(fnmatch(relative, pattern) for pattern in patterns)


def _summaries(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["language"]].append(row)
    return {language: _summary(items) for language, items in sorted(grouped.items())}


def _summary(rows: list[dict]) -> dict:
    values = sorted(row["complexity"] for row in rows)
    categories = Counter()
    boundaries = Counter()
    for row in rows:
        categories.update(row["decisions"])
        boundaries[row["boundaryKind"]] += 1
    return {
        "callables": len(values),
        "min": values[0],
        "median": statistics.median(values),
        "p75": _nearest_rank(values, 0.75),
        "p90": _nearest_rank(values, 0.90),
        "p95": _nearest_rank(values, 0.95),
        "max": values[-1],
        "mean": round(statistics.fmean(values), 2),
        "above": {
            str(level): {"count": sum(value > level for value in values),
                         "percent": round(100 * sum(value > level for value in values) / len(values), 2)}
            for level in (5, 10, 15, 20)
        },
        "decisionTotals": dict(sorted(categories.items())),
        "boundaryTotals": dict(sorted(boundaries.items())),
    }


def _nearest_rank(values: list[int], percentile: float) -> int:
    rank = max(1, int(len(values) * percentile + 0.999999999))
    return values[rank - 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Explicit production source roots/files")
    parser.add_argument("--exclude", action="append", default=[], help="Root-relative glob to exclude")
    parser.add_argument(
        "--exclude-decision", action="append", default=[],
        help="Research-only DecisionFact category to omit from the comparison",
    )
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    args = parser.parse_args()
    result = measure(args.paths, Path.cwd(), tuple(args.exclude), tuple(args.exclude_decision))
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
