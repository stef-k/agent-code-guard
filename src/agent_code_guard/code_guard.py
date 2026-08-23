#!/usr/bin/env python3
"""Single public runner for Agent Code Guard."""

from __future__ import annotations

import argparse
from importlib import import_module
import json
import sys
from pathlib import Path

from .file_selection import resolve_scope
from .guards import callable_size, complexity, loc, markdown_document_size, markdown_section_size, nesting
from .result_model import GuardResult, aggregate_state, required_policies


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run deterministic Code Guard checks.")
    value.add_argument(
        "paths", nargs="*", default=["."],
        help="Files or directories to inspect; bounds files selected by a Git selection mode.",
    )
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
    value.add_argument(
        "--scope-exclude", action="append", default=[],
        help="All-guards scope exclusion glob; repeat to add patterns (unlike LOC-only --exclude).",
    )
    value.add_argument("--count-blank-lines", action="store_true", help="Count blank lines for LOC.")
    value.add_argument("--ignore-comment-lines", action="store_true", help="Ignore simple comment-only lines.")
    return value


def payload(results: list[GuardResult]) -> dict[str, object]:
    return {
        "overall": aggregate_state(results),
        "requiredPolicies": required_policies(results),
        "guards": {result.guard_id: result.to_json() for result in results},
    }


def run_guards(scope, args: argparse.Namespace) -> list[GuardResult]:
    """Load guard configuration, then construct shared syntax facts at most once."""
    loc_config = loc.load_config(args)
    callable_size_config = callable_size.load_config(args)
    nesting_config = nesting.load_config(args)
    complexity_config = complexity.load_config(args)
    markdown_document_config = markdown_document_size.load_config(args)
    markdown_section_config = markdown_section_size.load_config(args)
    results = [loc.run(scope.root, loc_config, scope.files)]
    needs_analysis = callable_size_config.enabled or nesting_config.enabled or complexity_config.enabled
    if needs_analysis:
        analysis = import_module("agent_code_guard.analysis.pipeline")
        facts = analysis.analyze_files(scope.files)
        if callable_size_config.enabled:
            results.append(callable_size.run(scope.root, callable_size_config, facts))
        if nesting_config.enabled:
            results.append(nesting.run(scope.root, nesting_config, facts))
        if complexity_config.enabled:
            results.append(complexity.run(scope.root, complexity_config, facts))
    needs_markdown = markdown_document_config.enabled or markdown_section_config.enabled
    markdown_files = tuple(path for path in scope.files if path.suffix.lower() == ".md") if needs_markdown else ()
    if markdown_files:
        markdown = import_module("agent_code_guard.markdown")
        markdown_facts = markdown.analyze_files(markdown_files)
        if markdown_document_config.enabled:
            results.append(markdown_document_size.run(scope.root, markdown_document_config, markdown_facts))
        if markdown_section_config.enabled:
            results.append(markdown_section_size.run(scope.root, markdown_section_config, markdown_facts))
    else:
        if markdown_document_config.enabled:
            results.append(markdown_document_size.run(scope.root, markdown_document_config, _empty_markdown_facts()))
        if markdown_section_config.enabled:
            results.append(markdown_section_size.run(scope.root, markdown_section_config, _empty_markdown_facts()))
    return results


def _empty_markdown_facts():
    """Avoid importing the scanner family for scopes with no applicable files."""
    from types import SimpleNamespace
    return SimpleNamespace(documents=())


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
    callable_result = data["guards"].get("callableSize")
    if callable_result:
        for finding in callable_result["findings"]:
            if finding["state"] != "review":
                continue
            print(
                f"REVIEW: {finding['path']}:{finding['range']['startLine']}-{finding['range']['endLine']} "
                f"— {finding['callable']} is {finding['measured']} LOC "
                f"(review {finding['thresholds']['reviewAt']})"
            )
    nesting_result = data["guards"].get("nesting")
    if nesting_result:
        for finding in nesting_result["findings"]:
            if finding["state"] != "review":
                continue
            deepest = finding.get("details", {}).get("deepestLine")
            explanation = f"; deepest at line {deepest}" if deepest is not None else ""
            print(
                f"REVIEW: {finding['path']}:{finding['range']['startLine']}-{finding['range']['endLine']} "
                f"— {finding['callable']} nesting depth {finding['measured']} "
                f"(review {finding['thresholds']['reviewAt']}{explanation})"
            )
    complexity_result = data["guards"].get("complexity")
    if complexity_result:
        for finding in complexity_result["findings"]:
            if finding["state"] != "review":
                continue
            print(
                f"REVIEW: {finding['path']}:{finding['range']['startLine']}-{finding['range']['endLine']} "
                f"— {finding['callable']} complexity {finding['measured']} "
                f"(review {finding['thresholds']['reviewAt']})"
            )
    _print_markdown_findings(data)
    policies = data["requiredPolicies"]
    if policies:
        print(f"Required policies: {', '.join(policies)}")
        print("Required action: inspect each actionable finding using its policy guidance.")


def _print_markdown_findings(data: dict[str, object]) -> None:
    markdown_document_result = data["guards"].get("markdownDocumentSize")
    if markdown_document_result:
        for finding in markdown_document_result["findings"]:
            if finding["state"] != "review":
                continue
            print(
                f"REVIEW: {finding['path']} — Markdown document is {finding['measured']} lines "
                f"(review {finding['thresholds']['reviewAt']})"
            )
    markdown_section_result = data["guards"].get("markdownSectionSize")
    if markdown_section_result:
        for finding in markdown_section_result["findings"]:
            if finding["state"] != "review":
                continue
            print(
                f"REVIEW: {finding['path']}:{finding['range']['startLine']}-{finding['range']['endLine']} "
                f"— section {json.dumps(finding['heading'], ensure_ascii=False)} is {finding['measured']} lines "
                f"(review {finding['thresholds']['reviewAt']})"
            )


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
        data = payload(run_guards(scope, args))
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
