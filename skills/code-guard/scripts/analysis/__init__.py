"""Production source/container and syntax-fact pipeline."""

from .errors import AnalysisError, ProviderUnavailableError, SyntaxAnalysisError
from .facts import AnalysisFacts, CallableFact, CallableKey, ControlFlowFact, DecisionFact, FileFacts, SourcePoint, SourceRange
from .pipeline import analyze_files
from .provider import TreeSitterProvider
from .regions import ExecutableRegion, is_applicable

__all__ = [
    "AnalysisError", "AnalysisFacts", "CallableFact", "CallableKey", "ControlFlowFact", "DecisionFact",
    "ExecutableRegion", "FileFacts", "ProviderUnavailableError", "SourcePoint", "SourceRange",
    "SyntaxAnalysisError", "TreeSitterProvider", "analyze_files", "is_applicable",
]
