"""Normalized results shared by Code Guard runners and guard modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


STATE_RANK = {"pass": 0, "review": 1, "fail": 2}


@dataclass(frozen=True)
class Finding:
    path: str
    state: str
    native_status: str
    counted_loc: int
    warn_at: int
    fail_at: int
    override_index: int | None = None
    reason: str | None = None
    baseline_loc: int | None = None
    ratchet_status: str | None = None
    emit_baseline_fields: bool = False

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        result = {
            "path": data["path"],
            "state": data["state"],
            "nativeStatus": data["native_status"],
            "countedLoc": data["counted_loc"],
            "warnAt": data["warn_at"],
            "failAt": data["fail_at"],
            "overrideIndex": data["override_index"],
            "reason": data["reason"],
        }
        if self.emit_baseline_fields:
            result["baselineLoc"] = data["baseline_loc"]
            result["ratchetStatus"] = data["ratchet_status"]
        return result


@dataclass(frozen=True)
class CallableFinding:
    """Additive result shape proven by analyzer research; unused by LOC."""

    path: str
    callable: str
    start_line: int
    end_line: int
    measured: int
    state: str
    thresholds: dict[str, int] | None = None
    details: dict[str, Any] | None = None
    embedded_language: str | None = None

    def to_json(self) -> dict[str, Any]:
        value = {
            "path": self.path,
            "callable": self.callable,
            "range": {"startLine": self.start_line, "endLine": self.end_line},
            "measured": self.measured,
            "state": self.state,
            "thresholds": self.thresholds,
        }
        if self.details is not None:
            value["details"] = self.details
        if self.embedded_language is not None:
            value["embeddedLanguage"] = self.embedded_language
        return value


@dataclass(frozen=True)
class MarkdownDocumentFinding:
    path: str
    measured: int
    state: str
    thresholds: dict[str, int]

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "measured": self.measured,
            "state": self.state,
            "thresholds": self.thresholds,
        }


@dataclass(frozen=True)
class MarkdownSectionFinding:
    path: str
    heading: str
    level: int
    start_line: int
    end_line: int
    measured: int
    state: str
    thresholds: dict[str, int]

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "heading": self.heading,
            "level": self.level,
            "range": {"startLine": self.start_line, "endLine": self.end_line},
            "measured": self.measured,
            "state": self.state,
            "thresholds": self.thresholds,
        }


@dataclass(frozen=True)
class GuardResult:
    guard_id: str
    state: str
    findings: list[Finding | CallableFinding | MarkdownDocumentFinding | MarkdownSectionFinding]

    @property
    def required_policies(self) -> list[str]:
        return [self.guard_id] if self.state in {"review", "fail"} else []

    def to_json(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "findings": [finding.to_json() for finding in self.findings],
        }


def aggregate_state(results: list[GuardResult]) -> str:
    return max((result.state for result in results), key=STATE_RANK.get, default="pass")


def required_policies(results: list[GuardResult]) -> list[str]:
    return sorted({policy for result in results for policy in result.required_policies})
