#!/usr/bin/env python3
"""Single public runner for Agent Code Guard."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version as distribution_version
import json
import sys
from pathlib import Path

from .config_validation import validate_configuration
from .file_selection import resolve_scope
from .guards import callable_size, complexity, loc, markdown_document_size, markdown_section_size, nesting
from .human_output import format_completed_analysis
from . import loc_baseline
from .result_model import GuardResult, aggregate_state, required_policies
from .skill_distribution import export_skill, skill_path as installed_skill_path

DISTRIBUTION_NAME = "agent-code-guard"
METADATA_UNAVAILABLE = f"installed distribution metadata is unavailable for {DISTRIBUTION_NAME}"


def _installed_distribution_version() -> str:
    try:
        installed_version = distribution_version(DISTRIBUTION_NAME)
    except (PackageNotFoundError, OSError, UnicodeError) as exc:
        raise ValueError(METADATA_UNAVAILABLE) from exc
    if not isinstance(installed_version, str):
        raise ValueError(METADATA_UNAVAILABLE)
    return installed_version


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        prog="code-guard",
        description="Run deterministic Code Guard checks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Diagnostics:
  code-guard doctor
  code-guard doctor --json
    Inspect the active installation and current directory without running analysis.
    Healthy reports exit 0; unhealthy reports exit 1; invocation/internal errors exit 3.

Version reporting:
  code-guard --version
    Output: agent-code-guard <version>
  code-guard --version --json
    Output: {"distribution": "agent-code-guard", "version": "<version>"}

Successful version reporting exits 0. Incompatible arguments or unavailable
metadata exit 3. --version may be combined only with --json.

Legacy LOC adoption:
  code-guard [PATH ...] --create-loc-baseline [counting/configuration options]
  code-guard [PATH ...] --update-loc-baseline [counting/configuration options]
    Create or lower/prune the source-controlled LOC ratchet at
    <analysis-root>/.agent-tools/code-guard.loc-baseline.json. These explicit
    write modes do not run normal analysis and never increase an allowance.""",
    )
    value.add_argument(
        "paths", nargs="*", default=[],
        help="Files or directories to inspect; exact first token 'doctor' selects diagnostics mode.",
    )
    value.add_argument("--config", help="Path to code-guard.config.json.")
    value.add_argument("--warn", type=int, help="Override the global LOC warning threshold.")
    value.add_argument("--fail", type=int, help="Override the global LOC failure threshold.")
    value.add_argument("--json", action="store_true", help="Emit normalized full JSON.")
    value.add_argument(
        "--json-mode", choices=("compact", "debug"),
        help="Completed-analysis JSON mode; requires --json. Compact omits pass findings; debug is full output.",
    )
    value.add_argument(
        "--version", action="store_true",
        help="Print the installed agent-code-guard distribution version; may be combined only with --json.",
    )
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
    value.add_argument(
        "--create-loc-baseline", action="store_true",
        help="Create the canonical LOC legacy-adoption baseline without running analysis.",
    )
    value.add_argument(
        "--update-loc-baseline", action="store_true",
        help="Lower or prune the canonical LOC baseline without running analysis.",
    )
    value.add_argument(
        "--skill-path", action="store_true",
        help="Print the absolute path to this distribution's bundled Code Guard skill.",
    )
    value.add_argument(
        "--export-skill", metavar="TARGET_DIRECTORY",
        help="Copy this distribution's bundled Code Guard skill into an empty target directory.",
    )
    return value


def _doctor_mode(args: argparse.Namespace, raw_arguments: list[str]) -> int | None:
    if not raw_arguments or raw_arguments[0] != "doctor":
        return None
    incompatible = (
        args.paths != ["doctor"]
        or args.config is not None
        or args.warn is not None
        or args.fail is not None
        or args.version
        or args.json_mode is not None
        or args.ci
        or args.changed_only
        or args.staged
        or args.base_ref is not None
        or bool(args.include)
        or bool(args.exclude)
        or bool(args.scope_exclude)
        or args.count_blank_lines
        or args.ignore_comment_lines
        or args.skill_path
        or args.export_skill is not None
    )
    if incompatible:
        raise ValueError("doctor may be combined only with --json")
    report = gather_doctor_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_doctor_report(report))
    return 0 if report["status"] == "healthy" else 1


def _version_mode(args: argparse.Namespace) -> int | None:
    if not args.version:
        return None
    incompatible = (
        bool(args.paths)
        or args.config is not None
        or args.warn is not None
        or args.fail is not None
        or args.ci
        or args.changed_only
        or args.staged
        or args.base_ref is not None
        or bool(args.include)
        or bool(args.exclude)
        or bool(args.scope_exclude)
        or args.count_blank_lines
        or args.ignore_comment_lines
        or args.skill_path
        or args.export_skill is not None
        or args.json_mode is not None
    )
    if incompatible:
        raise ValueError("--version may be combined only with --json")
    installed_version = _installed_distribution_version()
    if args.json:
        print(json.dumps({"distribution": DISTRIBUTION_NAME, "version": installed_version}, indent=2))
    else:
        print(f"{DISTRIBUTION_NAME} {installed_version}")
    return 0


def _management_mode(args: argparse.Namespace) -> int | None:
    if not args.skill_path and args.export_skill is None:
        args.paths = args.paths or ["."]
        return None
    incompatible = (
        args.skill_path and args.export_skill is not None
        or bool(args.paths)
        or args.config is not None
        or args.warn is not None
        or args.fail is not None
        or args.json
        or args.json_mode is not None
        or args.ci
        or args.changed_only
        or args.staged
        or args.base_ref is not None
        or bool(args.include)
        or bool(args.exclude)
        or bool(args.scope_exclude)
        or args.count_blank_lines
        or args.ignore_comment_lines
    )
    if incompatible:
        raise ValueError("skill management options cannot be combined with guard execution options or paths")
    if args.skill_path:
        print(installed_skill_path())
    else:
        print(export_skill(Path(args.export_skill)))
    return 0


def _loc_baseline_mode(args: argparse.Namespace) -> int | None:
    if not args.create_loc_baseline and not args.update_loc_baseline:
        return None
    incompatible = (
        args.create_loc_baseline and args.update_loc_baseline
        or (bool(args.paths) and args.paths[0] == "doctor")
        or args.json
        or args.json_mode is not None
        or args.ci
        or args.version
        or args.changed_only
        or args.staged
        or args.base_ref is not None
        or args.skill_path
        or args.export_skill is not None
    )
    if incompatible:
        raise ValueError(
            "LOC baseline write modes accept only paths and LOC counting/configuration options"
        )
    args.paths = args.paths or ["."]
    invocation = Path.cwd()
    validate_configuration(args.config, invocation)
    scope = resolve_scope(args, invocation)
    linked_targets = loc_baseline.validate_explicit_scope(
        args.paths, invocation, scope.root, scope.files,
    )
    config = loc.load_config(args)
    if args.create_loc_baseline:
        files = tuple(path for path in scope.files if path.resolve() not in linked_targets)
        count = loc_baseline.create(scope.root, files, config)
        print(f"Created LOC baseline: {loc_baseline.RELATIVE_PATH} ({count} entries).")
    else:
        lowered, removed, unchanged = loc_baseline.update(
            scope.root, args.paths, invocation, config, scope.excluded_files,
        )
        print(
            f"Updated LOC baseline: {loc_baseline.RELATIVE_PATH} "
            f"({lowered} lowered, {removed} removed, {unchanged} unchanged)."
        )
    return 0


@dataclass(frozen=True)
class ScopeSummary:
    selected: int
    analyzed: int
    inapplicable: int
    excluded: int

    def to_json(self) -> dict[str, int]:
        return {
            "selected": self.selected,
            "analyzed": self.analyzed,
            "inapplicable": self.inapplicable,
            "excluded": self.excluded,
        }


@dataclass(frozen=True)
class CompletedAnalysis:
    results: list[GuardResult]
    scope: ScopeSummary


def payload(
    analysis: CompletedAnalysis | list[GuardResult], json_mode: str | None = None,
) -> dict[str, object]:
    """Serialize a completed run; retain the legacy result-list seam for focused guard tests."""
    if isinstance(analysis, list):
        analysis = CompletedAnalysis(analysis, ScopeSummary(0, 0, 0, 0))
    results = analysis.results
    data = {
        "overall": aggregate_state(results),
        "scope": analysis.scope.to_json(),
        "requiredPolicies": required_policies(results),
        "guards": {result.guard_id: result.to_json() for result in results},
    }
    if json_mode == "compact":
        for guard in data["guards"].values():
            guard["findings"] = [
                finding for finding in guard["findings"] if finding["state"] in {"review", "fail"}
            ]
    return data


def run_guards(scope, args: argparse.Namespace) -> list[GuardResult]:
    return run_analysis(scope, args).results


def run_analysis(
    scope, args: argparse.Namespace, baseline_override: dict[str, int] | None = None,
    baseline_loaded: bool = False, linked_targets: set[Path] | None = None,
) -> CompletedAnalysis:
    """Load guard configuration, then construct shared syntax facts at most once."""
    loc_config = loc.load_config(args)
    baseline = baseline_override if baseline_loaded else loc_baseline.load_if_present(scope.root)
    if baseline is not None:
        loc_baseline.validate_paths(scope.root, baseline)
        loc_baseline.validate_overlap(baseline, loc_config)
        for path in scope.files:
            if not path.is_file() or not path.resolve().is_relative_to(scope.root.resolve()):
                raise ValueError(f"baseline analysis scope is outside analysis root: {path}")
        baseline = dict(baseline)
        for target in linked_targets or set():
            baseline.pop(target.relative_to(scope.root).as_posix(), None)
    callable_size_config = callable_size.load_config(args)
    nesting_config = nesting.load_config(args)
    complexity_config = complexity.load_config(args)
    markdown_document_config = markdown_document_size.load_config(args)
    markdown_section_config = markdown_section_size.load_config(args)
    results = [loc.run(scope.root, loc_config, scope.files, baseline)]
    analyzed_files = {
        path for path in scope.files
        if loc_config.enabled and loc.should_include(path, loc_config, scope.root)
    }
    needs_analysis = callable_size_config.enabled or nesting_config.enabled or complexity_config.enabled
    if needs_analysis:
        analysis = import_module("agent_code_guard.analysis.pipeline")
        analyzed_files.update(path for path in scope.files if analysis.is_applicable(path))
        facts = analysis.analyze_files(scope.files)
        if callable_size_config.enabled:
            results.append(callable_size.run(scope.root, callable_size_config, facts))
        if nesting_config.enabled:
            results.append(nesting.run(scope.root, nesting_config, facts))
        if complexity_config.enabled:
            results.append(complexity.run(scope.root, complexity_config, facts))
    needs_markdown = markdown_document_config.enabled or markdown_section_config.enabled
    markdown_files = tuple(path for path in scope.files if path.suffix.lower() == ".md") if needs_markdown else ()
    analyzed_files.update(markdown_files)
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
    selected = len(scope.files)
    analyzed = len(analyzed_files)
    return CompletedAnalysis(
        results,
        ScopeSummary(selected, analyzed, selected - analyzed, len(scope.excluded_files)),
    )


def _empty_markdown_facts():
    """Avoid importing the scanner family for scopes with no applicable files."""
    from types import SimpleNamespace
    return SimpleNamespace(documents=())


def print_text(data: dict[str, object]) -> None:
    print(format_completed_analysis(data))


def exit_code(overall: str, ci: bool) -> int:
    if overall == "fail":
        return 2
    if overall == "review" and not ci:
        return 1
    return 0


def _print_tool_error(message: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"error": message}, indent=2))
    else:
        print(f"Code Guard error: {message}", file=sys.stderr)
    return 3


def main() -> int:
    raw_arguments = sys.argv[1:]
    if "--version" in raw_arguments and any(value in raw_arguments for value in ("-h", "--help")):
        return _print_tool_error("--version may be combined only with --json", "--json" in raw_arguments)
    args = parser().parse_args()
    try:
        if args.json_mode is not None and not args.json:
            raise ValueError("--json-mode requires --json")
        baseline_result = _loc_baseline_mode(args)
        if baseline_result is not None:
            return baseline_result
        doctor_result = _doctor_mode(args, raw_arguments)
        if doctor_result is not None:
            return doctor_result
        version_result = _version_mode(args)
        if version_result is not None:
            return version_result
        management_result = _management_mode(args)
        if management_result is not None:
            return management_result
        validate_configuration(args.config, Path.cwd())
        scope = resolve_scope(args, Path.cwd())
        linked_targets: set[Path] = set()
        baseline_loaded = hasattr(scope, "root")
        if baseline_loaded and loc_baseline.baseline_path(scope.root).exists():
            linked_targets = loc_baseline.validate_explicit_scope(
                args.paths, Path.cwd(), scope.root, scope.files,
            )
        baseline = loc_baseline.load_if_present(scope.root) if baseline_loaded else None
        data = payload(
            run_analysis(scope, args, baseline, baseline_loaded, linked_targets), args.json_mode,
        )
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print_text(data)
        return exit_code(data["overall"], args.ci)
    except Exception as exc:
        write_mode = args.create_loc_baseline or args.update_loc_baseline
        return _print_tool_error(str(exc), args.json and not write_mode)


def gather_doctor_report() -> dict[str, object]:
    from .doctor import gather_report
    return gather_report()


def format_doctor_report(report: dict[str, object]) -> str:
    from .doctor import format_human
    return format_human(report)


if __name__ == "__main__":
    sys.exit(main())
