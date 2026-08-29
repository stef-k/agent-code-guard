"""Immutable, parser-provider-neutral syntax facts consumed by future guards."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class SourcePoint:
    """A one-based line and one-based UTF-8 byte column in the original file."""

    line: int
    byte_column: int
    byte_offset: int


@dataclass(frozen=True, order=True)
class SourceRange:
    """A half-open original-source byte range with inclusive physical lines."""

    start: SourcePoint
    end: SourcePoint

    @property
    def start_line(self) -> int:
        return self.start.line

    @property
    def end_line(self) -> int:
        return self.end.line if self.end.byte_column > 1 else max(self.start.line, self.end.line - 1)

    @property
    def physical_loc(self) -> int:
        return self.end_line - self.start_line + 1


@dataclass(frozen=True)
class CallableKey:
    path: Path
    embedded_language: str
    identity: str
    source_range: SourceRange


@dataclass(frozen=True)
class CallableFact:
    path: Path
    embedded_language: str
    identity: str
    source_range: SourceRange
    parent_callable: str | None
    boundary_kind: str
    key: CallableKey
    parent_key: CallableKey | None


@dataclass(frozen=True)
class ControlFlowFact:
    callable_identity: str
    callable_key: CallableKey
    category: str
    provider_kind: str
    source_range: SourceRange
    parent_control_range: SourceRange | None
    increases_nesting: bool = True


@dataclass(frozen=True)
class DecisionFact:
    callable_identity: str
    callable_key: CallableKey
    category: str
    provider_kind: str
    source_range: SourceRange


@dataclass(frozen=True)
class FileFacts:
    path: Path
    callables: tuple[CallableFact, ...]
    controls: tuple[ControlFlowFact, ...]
    decisions: tuple[DecisionFact, ...]
    region_count: int
    reporting_path: str | None = None


@dataclass(frozen=True)
class AnalysisFacts:
    files: tuple[FileFacts, ...]

    @property
    def callables(self) -> tuple[CallableFact, ...]:
        return tuple(fact for file in self.files for fact in file.callables)

    @property
    def controls(self) -> tuple[ControlFlowFact, ...]:
        return tuple(fact for file in self.files for fact in file.controls)

    @property
    def decisions(self) -> tuple[DecisionFact, ...]:
        return tuple(fact for file in self.files for fact in file.decisions)

    def reporting_path_for(self, path: Path, root: Path | None = None) -> str:
        stored = next(
            (file.reporting_path for file in self.files if file.path == path and file.reporting_path is not None),
            None,
        )
        if stored is not None:
            return stored
        try:
            return path.relative_to(root).as_posix() if root is not None else path.as_posix()
        except ValueError:
            return path.as_posix()
