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
from .file_selection import ResolvedScope, resolve_invocation, resolve_scope
from .guards import callable_size, complexity, loc, markdown_document_size, markdown_section_size, nesting
from .human_output import format_completed_analysis
from . import loc_baseline
from .result_model import GuardResult, aggregate_state, required_policies
from .invocation import AnalysisContext, SelectedFile, load_configuration
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
    unavailable: int | None = None

    def to_json(self) -> dict[str, int]:
        data = {
            "selected": self.selected,
            "analyzed": self.analyzed,
            "inapplicable": self.inapplicable,
        }
        if self.unavailable is not None:
            data["unavailable"] = self.unavailable
        data["excluded"] = self.excluded
        return data


@dataclass(frozen=True)
class UnavailableEntry:
    path: str
    language: str
    kind: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {
            "path": self.path, "language": self.language,
            "kind": self.kind, "message": self.message,
        }


@dataclass(frozen=True)
class CompletedAnalysis:
    results: list[GuardResult]
    scope: ScopeSummary
    unavailable: tuple[UnavailableEntry, ...] = ()
    incomplete_guard_ids: tuple[str, ...] = ()


def payload(
    analysis: CompletedAnalysis | list[GuardResult], json_mode: str | None = None,
) -> dict[str, object]:
    """Serialize a completed run; retain the legacy result-list seam for focused guard tests."""
    if isinstance(analysis, list):
        analysis = CompletedAnalysis(analysis, ScopeSummary(0, 0, 0, 0))
    results = analysis.results
    completed_overall = aggregate_state(results)
    incomplete = bool(analysis.unavailable)
    data = {
        "overall": "incomplete" if incomplete else completed_overall,
        "scope": analysis.scope.to_json(),
        "requiredPolicies": required_policies(results),
        "guards": {result.guard_id: result.to_json() for result in results},
    }
    if incomplete:
        data = {
            "overall": "incomplete",
            "completedOverall": completed_overall,
            "scope": data["scope"],
            "unavailable": [entry.to_json() for entry in analysis.unavailable],
            "requiredPolicies": data["requiredPolicies"],
            "guards": data["guards"],
        }
        unavailable_paths = [entry.path for entry in analysis.unavailable]
        for guard_id, guard in data["guards"].items():
            guard["complete"] = guard_id not in analysis.incomplete_guard_ids
            if not guard["complete"]:
                guard["unavailablePaths"] = unavailable_paths
    if json_mode == "compact":
        for guard in data["guards"].values():
            guard["findings"] = [
                finding for finding in guard["findings"] if finding["state"] in {"review", "fail"}
            ]
    return data


def run_guards(scope, args: argparse.Namespace) -> list[GuardResult]:
    return run_analysis(scope, args).results


def run_analysis(
    scope: AnalysisContext | ResolvedScope, args: argparse.Namespace, baseline_override: dict[str, int] | None = None,
    baseline_loaded: bool = False, linked_targets: set[Path] | None = None,
) -> CompletedAnalysis:
    """Load guard configuration, then construct shared syntax facts at most once."""
    context = scope if isinstance(scope, AnalysisContext) else _legacy_context(scope, args)
    loc_config = loc.load_config(args, context.configuration)
    baseline = baseline_override if baseline_loaded else loc_baseline.load_if_present(context.root)
    if baseline is not None:
        loc_baseline.validate_paths(context.root, baseline)
        loc_baseline.validate_overlap(baseline, loc_config)
        error = "baseline analysis scope is outside analysis root"
        try:
            current_root = context.root.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"{error}: {context.root}") from exc
        for selected in context.selected_files:
            try:
                current_path = selected.physical_path.resolve(strict=True)
                valid = (
                    not selected.physical_path.is_symlink()
                    and current_path.is_file()
                    and current_path.is_relative_to(current_root)
                )
            except OSError:
                valid = False
            if not valid:
                raise ValueError(f"{error}: {selected.physical_path}")
        baseline = dict(baseline)
        for target in linked_targets or set():
            baseline.pop(target.relative_to(context.root).as_posix(), None)
    callable_size_config = callable_size.load_config(args, context.configuration)
    nesting_config = nesting.load_config(args, context.configuration)
    complexity_config = complexity.load_config(args, context.configuration)
    markdown_document_config = markdown_document_size.load_config(args, context.configuration)
    markdown_section_config = markdown_section_size.load_config(args, context.configuration)
    results = [loc.run(context.root, loc_config, context.selected_files, baseline)]
    analyzed_files = {
        selected.reporting_path for selected in context.selected_files
        if loc_config.enabled and loc.should_include(selected, loc_config)
    }
    needs_analysis = callable_size_config.enabled or nesting_config.enabled or complexity_config.enabled
    if needs_analysis:
        analysis = import_module("agent_code_guard.analysis.pipeline")
        analyzed_files.update(selected.reporting_path for selected in context.selected_files if analysis.is_applicable(selected.physical_path))
        batch = analysis.analyze_files_for_runner(context.selected_files)
        facts = batch.facts
        if callable_size_config.enabled:
            results.append(callable_size.run(context.root, callable_size_config, facts))
        if nesting_config.enabled:
            results.append(nesting.run(context.root, nesting_config, facts))
        if complexity_config.enabled:
            results.append(complexity.run(context.root, complexity_config, facts))
    needs_markdown = markdown_document_config.enabled or markdown_section_config.enabled
    markdown_files = tuple(selected for selected in context.selected_files if selected.physical_path.suffix.lower() == ".md") if needs_markdown else ()
    analyzed_files.update(selected.reporting_path for selected in markdown_files)
    if markdown_files:
        markdown = import_module("agent_code_guard.markdown")
        markdown_facts = markdown.analyze_files(markdown_files)
        if markdown_document_config.enabled:
            results.append(markdown_document_size.run(context.root, markdown_document_config, markdown_facts))
        if markdown_section_config.enabled:
            results.append(markdown_section_size.run(context.root, markdown_section_config, markdown_facts))
    else:
        if markdown_document_config.enabled:
            results.append(markdown_document_size.run(context.root, markdown_document_config, _empty_markdown_facts()))
        if markdown_section_config.enabled:
            results.append(markdown_section_size.run(context.root, markdown_section_config, _empty_markdown_facts()))
    selected = len(context.selected_files)
    analyzed = len(analyzed_files)
    unavailable = tuple(
        UnavailableEntry(
            item.reporting_path, item.language, item.kind, item.message,
        )
        for item in (batch.unavailable if needs_analysis else ())
    )
    incomplete_guard_ids = tuple(
        guard_id for guard_id, enabled in (
            ("callableSize", callable_size_config.enabled),
            ("nesting", nesting_config.enabled),
            ("complexity", complexity_config.enabled),
        ) if enabled and unavailable
    )
    return CompletedAnalysis(
        results,
        ScopeSummary(
            selected, analyzed, selected - analyzed, len(context.excluded_files),
            len({entry.path for entry in unavailable}) if unavailable else None,
        ),
        unavailable,
        incomplete_guard_ids,
    )


def _legacy_context(scope: ResolvedScope, args: argparse.Namespace) -> AnalysisContext:
    """Focused-test adapter; the production runner constructs identities during selection."""
    document = validate_configuration(args.config, Path.cwd())
    def selected(path: Path) -> SelectedFile:
        try:
            report = path.relative_to(scope.root).as_posix()
        except ValueError:
            report = path.as_posix()
        return SelectedFile(report, path)
    return AnalysisContext(
        scope.root, document, tuple(selected(path) for path in scope.files),
        tuple(selected(path) for path in scope.excluded_files),
    )


def _empty_markdown_facts():
    """Avoid importing the scanner family for scopes with no applicable files."""
    from types import SimpleNamespace
    return SimpleNamespace(documents=())


def print_text(data: dict[str, object]) -> None:
    print(format_completed_analysis(data))


def exit_code(overall: str, ci: bool) -> int:
    if overall == "incomplete":
        return 3
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
        invocation = Path.cwd()
        configuration = load_configuration(args.config, invocation)
        validate_configuration(args.config, invocation, configuration)
        scope = resolve_invocation(args, invocation, configuration)
        linked_targets: set[Path] = set()
        baseline_loaded = hasattr(scope, "root")
        if baseline_loaded and loc_baseline.baseline_path(scope.root).exists():
            linked_targets = loc_baseline.validate_explicit_scope(
                args.paths, invocation, scope.root,
                tuple(selected.physical_path for selected in scope.selected_files),
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
