"""Deterministic failures raised by the production syntax pipeline."""


class AnalysisError(RuntimeError):
    """Base error suitable for Code Guard's existing exit-3 boundary."""

    def __init__(self, message: str, *, language: str | None = None) -> None:
        super().__init__(message)
        self.language = language


class ProviderUnavailableError(AnalysisError):
    """The configured parser provider or a required grammar is unavailable."""


class SyntaxAnalysisError(AnalysisError):
    """A supported source/container cannot produce authoritative facts."""
