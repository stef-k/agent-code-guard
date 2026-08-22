"""Parse applicable selected files once and return reusable immutable facts."""

from __future__ import annotations

from pathlib import Path

from .adapters import extract_facts
from .errors import SyntaxAnalysisError
from .facts import AnalysisFacts, FileFacts
from .provider import ParserProvider, TreeSitterProvider
from .regions import executable_regions, is_applicable


def analyze_files(files: tuple[Path, ...] | list[Path], provider: ParserProvider | None = None) -> AnalysisFacts:
    """Analyze only applicable entries from the already-resolved caller scope."""
    active_provider = provider or TreeSitterProvider()
    results: list[FileFacts] = []
    for path in files:
        path = Path(path)
        if not is_applicable(path):
            continue
        callables = []
        controls = []
        decisions = []
        regions = executable_regions(path, active_provider)
        for region in regions:
            tree = active_provider.parse(region.language, region.source)
            if tree.root_node.has_error:
                raise SyntaxAnalysisError(
                    f"unable to parse {path}: embedded {region.language} syntax tree contains errors"
                )
            region_callables, region_controls, region_decisions = extract_facts(tree.root_node, region)
            callables.extend(region_callables)
            controls.extend(region_controls)
            decisions.extend(region_decisions)
        results.append(FileFacts(path, tuple(callables), tuple(controls), tuple(decisions), len(regions)))
    return AnalysisFacts(tuple(results))
