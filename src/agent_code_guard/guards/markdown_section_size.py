"""Markdown heading-delimited direct-section physical-size review guard."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..reporting import reporting_path
from ..result_model import GuardResult, MarkdownSectionFinding

if TYPE_CHECKING:
    from ..markdown.facts import MarkdownFacts

DEFAULT_REVIEW_AT = 200


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
    data = guards.get("markdownSectionSize")
    if data is None:
        return Config(True, DEFAULT_REVIEW_AT)
    if not isinstance(data, dict):
        raise ValueError("guards.markdownSectionSize must be an object")
    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("guards.markdownSectionSize.enabled must be a boolean")
    if not enabled:
        return Config(False)
    review_at = data.get("reviewAt", DEFAULT_REVIEW_AT)
    if isinstance(review_at, bool) or not isinstance(review_at, int) or review_at <= 0:
        raise ValueError("guards.markdownSectionSize.reviewAt must be a positive integer")
    return Config(True, review_at)


def run(root: Path, config: Config, facts: MarkdownFacts) -> GuardResult:
    assert config.review_at is not None
    findings = [MarkdownSectionFinding(
        reporting_path(document.path, root), section.heading, section.level,
        section.start_line, section.end_line, section.physical_lines,
        "review" if section.physical_lines > config.review_at else "pass", {"reviewAt": config.review_at},
    ) for document in facts.documents for section in document.sections]
    findings.sort(key=lambda finding: (finding.path, finding.start_line, finding.end_line, finding.heading))
    return GuardResult("markdownSectionSize", "review" if any(item.state == "review" for item in findings) else "pass", findings)
