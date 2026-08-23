"""Concrete immutable facts for Markdown size guards."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarkdownSectionFact:
    heading: str
    level: int
    start_line: int
    end_line: int
    physical_lines: int


@dataclass(frozen=True)
class MarkdownDocumentFact:
    path: Path
    physical_lines: int
    sections: tuple[MarkdownSectionFact, ...]


@dataclass(frozen=True)
class MarkdownFacts:
    documents: tuple[MarkdownDocumentFact, ...]
