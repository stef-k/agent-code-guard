#!/usr/bin/env python3
"""Single public runner for Agent Code Guard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from file_selection import resolve_scope
from guards import loc
from result_model import GuardResult, aggregate_state, required_policies


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run deterministic Code Guard checks.")
    value.add_argument("paths", nargs="*", default=["."], help="Files or directories to inspect.")
    value.add_argument("--config", help="Path to code-guard.config.json.")
    value.add_argument("--warn", type=int, help="Override the global LOC warning threshold.")
    value.add_argument("--fail", type=int, help="Override the global LOC failure threshold.")
    value.add_argument("--json", action="store_true", help="Emit normalized JSON.")
    value.add_argument("--ci", action="store_true", help="Do not fail solely on REVIEW.")
    value.add_argument("--changed-only", action="store_true", help="Inspect staged, unstaged, and untracked files.")
    value.add_argument("--staged", action="store_true", help="Inspect index-only changes.")
    value.add_argument("--base-ref", help="Inspect committed ACMR changes from <ref>...HEAD.")
    value.add_argument("--include", action="append", default=[], help="Extra LOC extension.")
    value.add_argument("--exclude", action="append", default=[], help="Extra LOC exclusion glob.")
    value.add_argument("--count-blank-lines", action="store_true", help="Count blank lines for LOC.")
    value.add_argument("--ignore-comment-lines", action="store_true", help="Ignore simple comment-only lines.")
    return value


def payload(results: list[GuardResult]) -> dict[str, object]:
    return {
        "overall": aggregate_state(results),
        "requiredPolicies": required_policies(results),
        "guards": {result.guard_id: result.to_json() for result in results},
    }


def print_text(data: dict[str, object]) -> None:
    print(str(data["overall"]).upper())
    loc_result = data["guards"]["loc"]
    for finding in loc_result["findings"]:
        if finding["nativeStatus"] == "ok":
            continue
        label = "EXEMPT" if finding["nativeStatus"] == "exempt" else finding["state"].upper()
        print(f"{label}: {finding['path']} — {finding['countedLoc']} LOC (warn {finding['warnAt']}, fail {finding['failAt']})")
        if finding["overrideIndex"] is not None:
            print(f"  Threshold override: {finding['overrideIndex']}")
        if finding["reason"]:
            print(f"  Reason: {finding['reason']}")
    policies = data["requiredPolicies"]
    if policies:
        print(f"Required policies: {', '.join(policies)}")
        print("Required action: inspect each actionable finding using its policy guidance.")


def exit_code(overall: str, ci: bool) -> int:
    if overall == "fail":
        return 2
    if overall == "review" and not ci:
        return 1
    return 0


def main() -> int:
    args = parser().parse_args()
    try:
        scope = resolve_scope(args, Path.cwd())
        result = loc.run(scope.root, loc.load_config(args), scope.files)
        data = payload([result])
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print_text(data)
        return exit_code(data["overall"], args.ci)
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"Code Guard error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
