"""Structural nesting guard over shared provider-neutral control-flow facts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..invocation import JsonObject, configuration_for_guard
from ..result_model import CallableFinding, GuardResult

if TYPE_CHECKING:
    from ..analysis.facts import AnalysisFacts, CallableFact, ControlFlowFact, SourceRange

DEFAULT_REVIEW_AT = 4


@dataclass(frozen=True)
class Config:
    enabled: bool
    review_at: int | None = None


def load_config(args: argparse.Namespace, document: JsonObject | None = None) -> Config:
    document = configuration_for_guard(args, document)
    if not isinstance(document, dict):
        raise ValueError("configuration must be an object")
    guards = document.get("guards", {})
    if not isinstance(guards, dict):
        raise ValueError("guards must be an object")
    data = guards.get("nesting")
    if data is None:
        return Config(True, DEFAULT_REVIEW_AT)
    if not isinstance(data, dict):
        raise ValueError("guards.nesting must be an object")
    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("guards.nesting.enabled must be a boolean")
    if not enabled:
        return Config(False)
    review_at = data.get("reviewAt", DEFAULT_REVIEW_AT)
    if isinstance(review_at, bool) or not isinstance(review_at, int) or review_at <= 0:
        raise ValueError("guards.nesting.reviewAt must be a positive integer")
    return Config(True, review_at)


def run(root: Path, config: Config, analysis_facts: AnalysisFacts) -> GuardResult:
    if not config.enabled:
        return GuardResult("nesting", "pass", [])
    controls_by_callable: dict[object, list[ControlFlowFact]] = {}
    for control in analysis_facts.controls:
        controls_by_callable.setdefault(control.callable_key, []).append(control)
    findings = [
        evaluate(
            root, config, callable_fact, controls_by_callable.get(callable_fact.key, []),
            analysis_facts.reporting_path_for(callable_fact.path, root),
        )
        for callable_fact in analysis_facts.callables
    ]
    findings.sort(key=lambda finding: (finding.path, finding.start_line, finding.end_line, finding.callable))
    state = "review" if any(finding.state == "review" for finding in findings) else "pass"
    return GuardResult("nesting", state, findings)


def evaluate(
    root: Path,
    config: Config,
    callable_fact: CallableFact,
    controls: list[ControlFlowFact] | tuple[ControlFlowFact, ...],
    path: str | None = None,
) -> CallableFinding:
    assert config.review_at is not None
    depth, deepest_line = _maximum_depth(controls)
    return CallableFinding(
        path=path or callable_fact.path.as_posix(),
        callable=callable_fact.identity,
        start_line=callable_fact.source_range.start_line,
        end_line=callable_fact.source_range.end_line,
        measured=depth,
        state="review" if depth > config.review_at else "pass",
        thresholds={"reviewAt": config.review_at},
        details={"deepestLine": deepest_line} if deepest_line is not None else None,
        embedded_language=callable_fact.embedded_language,
    )


def _maximum_depth(controls: list[ControlFlowFact] | tuple[ControlFlowFact, ...]) -> tuple[int, int | None]:
    depth_by_range: dict[SourceRange, int] = {}
    maximum = 0
    deepest_line: int | None = None
    ordered = sorted(
        controls,
        key=lambda fact: (fact.source_range.start.byte_offset, fact.source_range.end.byte_offset),
    )
    for fact in ordered:
        parent_depth = depth_by_range.get(fact.parent_control_range, 0)
        depth = parent_depth + int(fact.increases_nesting)
        depth_by_range[fact.source_range] = depth
        if depth > maximum:
            maximum = depth
            deepest_line = fact.source_range.start_line
    return maximum, deepest_line
