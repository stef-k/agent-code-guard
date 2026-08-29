"""Markdown heading-delimited direct-section physical-size review guard."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..invocation import JsonObject, configuration_for_guard
from ..result_model import GuardResult, MarkdownSectionFinding

if TYPE_CHECKING:
    from ..markdown.facts import MarkdownFacts

DEFAULT_REVIEW_AT = 200


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
    data = guards.get("markdownSectionSize")
    if data is None:
        return Config(True, DEFAULT_REVIEW_AT)
    if not isinstance(data, Mapping):
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
        document.reporting_path or _path(document.path, root), section.heading, section.level,
        section.start_line, section.end_line, section.physical_lines,
        "review" if section.physical_lines > config.review_at else "pass", {"reviewAt": config.review_at},
    ) for document in facts.documents for section in document.sections]
    findings.sort(key=lambda finding: (finding.path, finding.start_line, finding.end_line, finding.heading))
    return GuardResult("markdownSectionSize", "review" if any(item.state == "review" for item in findings) else "pass", findings)


def _path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
