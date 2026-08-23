"""Immutable Markdown structure facts from a bounded standard-library scan."""

from .facts import MarkdownDocumentFact, MarkdownFacts, MarkdownSectionFact
from .scanner import analyze_files, scan_text

__all__ = ["MarkdownDocumentFact", "MarkdownFacts", "MarkdownSectionFact", "analyze_files", "scan_text"]
