"""Callable physical LOC guard over shared provider-neutral analysis facts."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..invocation import JsonObject, configuration_for_guard
from ..result_model import CallableFinding, GuardResult

if TYPE_CHECKING:
    from ..analysis.facts import AnalysisFacts, CallableFact

DEFAULT_REVIEW_AT = 80


@dataclass(frozen=True)
class Config:
    enabled: bool
    review_at: int | None = None


def load_config(args: argparse.Namespace, document: JsonObject | None = None) -> Config:
    document = configuration_for_guard(args, document)
    if not isinstance(document, Mapping):
        raise ValueError("configuration must be an object")
    guards = document.get("guards", {})
    if not isinstance(guards, Mapping):
        raise ValueError("guards must be an object")
    data = guards.get("callableSize")
    if data is None:
        return Config(True, DEFAULT_REVIEW_AT)
    if not isinstance(data, Mapping):
        raise ValueError("guards.callableSize must be an object")
    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("guards.callableSize.enabled must be a boolean")
    if not enabled:
        return Config(False)
    review_at = data.get("reviewAt", DEFAULT_REVIEW_AT)
    if isinstance(review_at, bool) or not isinstance(review_at, int) or review_at <= 0:
        raise ValueError("guards.callableSize.reviewAt must be a positive integer")
    return Config(True, review_at)


def run(root: Path, config: Config, analysis_facts: AnalysisFacts) -> GuardResult:
    if not config.enabled:
        return GuardResult("callableSize", "pass", [])
    findings = [
        evaluate(root, config, fact, analysis_facts.reporting_path_for(fact.path, root))
        for fact in analysis_facts.callables
    ]
    findings.sort(key=lambda finding: (finding.path, finding.start_line, finding.end_line, finding.callable))
    state = "review" if any(finding.state == "review" for finding in findings) else "pass"
    return GuardResult("callableSize", state, findings)


def evaluate(root: Path, config: Config, fact: CallableFact, path: str | None = None) -> CallableFinding:
    assert config.review_at is not None
    measured = fact.source_range.physical_loc
    return CallableFinding(
        path=path or fact.path.as_posix(),
        callable=fact.identity,
        start_line=fact.source_range.start_line,
        end_line=fact.source_range.end_line,
        measured=measured,
        state="review" if measured > config.review_at else "pass",
        thresholds={"reviewAt": config.review_at},
        embedded_language=fact.embedded_language,
    )
