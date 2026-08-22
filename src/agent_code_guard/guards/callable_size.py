"""Callable physical LOC guard over shared provider-neutral analysis facts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..result_model import CallableFinding, GuardResult

if TYPE_CHECKING:
    from ..analysis.facts import AnalysisFacts, CallableFact


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
    data = guards.get("callableSize")
    if data is None:
        return Config(False)
    if not isinstance(data, dict):
        raise ValueError("guards.callableSize must be an object")
    enabled = data.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("guards.callableSize.enabled must be a boolean")
    if not enabled:
        return Config(False)
    review_at = data.get("reviewAt")
    if isinstance(review_at, bool) or not isinstance(review_at, int) or review_at <= 0:
        raise ValueError("guards.callableSize.reviewAt must be a positive integer")
    return Config(True, review_at)


def run(root: Path, config: Config, analysis_facts: AnalysisFacts) -> GuardResult:
    if not config.enabled:
        return GuardResult("callableSize", "pass", [])
    findings = [evaluate(root, config, fact) for fact in analysis_facts.callables]
    findings.sort(key=lambda finding: (finding.path, finding.start_line, finding.end_line, finding.callable))
    state = "review" if any(finding.state == "review" for finding in findings) else "pass"
    return GuardResult("callableSize", state, findings)


def evaluate(root: Path, config: Config, fact: CallableFact) -> CallableFinding:
    assert config.review_at is not None
    measured = fact.source_range.physical_loc
    return CallableFinding(
        path=reporting_path(fact.path, root),
        callable=fact.identity,
        start_line=fact.source_range.start_line,
        end_line=fact.source_range.end_line,
        measured=measured,
        state="review" if measured > config.review_at else "pass",
        thresholds={"reviewAt": config.review_at},
        embedded_language=fact.embedded_language,
    )


def reporting_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()
