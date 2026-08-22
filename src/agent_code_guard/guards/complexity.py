"""Cyclomatic complexity guard over shared normalized decision facts."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..reporting import reporting_path
from ..result_model import CallableFinding, GuardResult

if TYPE_CHECKING:
    from ..analysis.facts import AnalysisFacts, CallableFact, DecisionFact

DEFAULT_REVIEW_AT = 15


@dataclass(frozen=True)
class Config:
    enabled: bool
    review_at: int | None = None


def load_config(args: argparse.Namespace) -> Config:
    document: dict[str, Any] = {}
    if args.config:
        path = Path(args.config)
        if not path.exists():
            raise FileNotFoundError(f"config file not found: {args.config}")
        document = json.loads(path.read_text(encoding="utf-8"))
    else:
        auto = Path(".agent-tools/code-guard.config.json")
        if auto.exists():
            document = json.loads(auto.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("configuration must be an object")
    guards = document.get("guards", {})
    if not isinstance(guards, dict):
        raise ValueError("guards must be an object")
    data = guards.get("cyclomaticComplexity")
    if data is None:
        return Config(True, DEFAULT_REVIEW_AT)
    if not isinstance(data, dict):
        raise ValueError("guards.cyclomaticComplexity must be an object")
    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("guards.cyclomaticComplexity.enabled must be a boolean")
    if not enabled:
        return Config(False)
    review_at = data.get("reviewAt", DEFAULT_REVIEW_AT)
    if isinstance(review_at, bool) or not isinstance(review_at, int) or review_at <= 0:
        raise ValueError("guards.cyclomaticComplexity.reviewAt must be a positive integer")
    return Config(True, review_at)


def run(root: Path, config: Config, analysis_facts: AnalysisFacts) -> GuardResult:
    if not config.enabled:
        return GuardResult("complexity", "pass", [])
    decisions_by_callable: dict[object, list[DecisionFact]] = {}
    for decision in analysis_facts.decisions:
        decisions_by_callable.setdefault(decision.callable_key, []).append(decision)
    findings = [
        evaluate(root, config, callable_fact, decisions_by_callable.get(callable_fact.key, []))
        for callable_fact in analysis_facts.callables
    ]
    findings.sort(key=lambda finding: (finding.path, finding.start_line, finding.end_line, finding.callable))
    state = "review" if any(finding.state == "review" for finding in findings) else "pass"
    return GuardResult("complexity", state, findings)


def evaluate(
    root: Path,
    config: Config,
    callable_fact: CallableFact,
    decisions: list[DecisionFact] | tuple[DecisionFact, ...],
) -> CallableFinding:
    assert config.review_at is not None
    counts = Counter(decision.category for decision in decisions)
    breakdown = {category: counts[category] for category in sorted(counts) if counts[category]}
    measured = 1 + len(decisions)
    return CallableFinding(
        path=reporting_path(callable_fact.path, root),
        callable=callable_fact.identity,
        start_line=callable_fact.source_range.start_line,
        end_line=callable_fact.source_range.end_line,
        measured=measured,
        state="review" if measured > config.review_at else "pass",
        thresholds={"reviewAt": config.review_at},
        details={"boundaryKind": callable_fact.boundary_kind, "decisions": breakdown},
        embedded_language=callable_fact.embedded_language,
    )
