"""Parse applicable selected files once and return reusable immutable facts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..invocation import SelectedFile

from .adapters import extract_facts
from .csharp_compat import corrected_csharp_root
from .errors import ProviderUnavailableError, SyntaxAnalysisError
from .facts import AnalysisFacts, FileFacts
from .provider import ParserProvider, TreeSitterProvider
from .regions import executable_regions, is_applicable


def analyze_files(files: tuple[SelectedFile, ...] | list[SelectedFile], provider: ParserProvider | None = None) -> AnalysisFacts:
    """Analyze only applicable entries from the already-resolved caller scope."""
    active_provider = provider or TreeSitterProvider()
    results = [
        _analyze_file(selected.physical_path, active_provider, selected.reporting_path)
        for selected in files if is_applicable(selected.physical_path)
    ]
    return AnalysisFacts(tuple(results))


@dataclass(frozen=True)
class UnavailableAnalysis:
    path: Path
    reporting_path: str
    language: str
    kind: str
    message: str


@dataclass(frozen=True)
class BatchAnalysis:
    facts: AnalysisFacts
    unavailable: tuple[UnavailableAnalysis, ...]


def analyze_files_for_runner(
    files: tuple[SelectedFile, ...], provider: ParserProvider | None = None,
) -> BatchAnalysis:
    """Analyze selected files independently while retaining only known unavailable evidence."""
    active_provider = provider or TreeSitterProvider()
    results: list[FileFacts] = []
    unavailable: list[UnavailableAnalysis] = []
    for selected in files:
        path = selected.physical_path
        if not is_applicable(path):
            continue
        try:
            results.append(_analyze_file(path, active_provider, selected.reporting_path))
        except (SyntaxAnalysisError, ProviderUnavailableError) as exc:
            if exc.language is None:
                raise
            kind = "syntax" if isinstance(exc, SyntaxAnalysisError) else "provider"
            unavailable.append(UnavailableAnalysis(path, selected.reporting_path, exc.language, kind, str(exc)))
    return BatchAnalysis(AnalysisFacts(tuple(results)), tuple(unavailable))


def _analyze_file(path: Path, provider: ParserProvider, reporting_path: str | None = None) -> FileFacts:
    callables = []
    controls = []
    decisions = []
    regions = executable_regions(path, provider)
    for region in regions:
        try:
            tree = provider.parse(region.language, region.source)
        except (SyntaxAnalysisError, ProviderUnavailableError) as exc:
            if exc.language is None:
                raise type(exc)(str(exc), language=region.language) from exc
            raise
        root = tree.root_node
        if tree.root_node.has_error:
            root = (
                corrected_csharp_root(provider, region.source, tree)
                if region.language == "csharp"
                else None
            )
            if root is None:
                raise SyntaxAnalysisError(
                    f"unable to parse {path}: embedded {region.language} syntax tree contains errors",
                    language=region.language,
                )
        region_callables, region_controls, region_decisions = extract_facts(root, region)
        callables.extend(region_callables)
        controls.extend(region_controls)
        decisions.extend(region_decisions)
    return FileFacts(path, tuple(callables), tuple(controls), tuple(decisions), len(regions), reporting_path)
