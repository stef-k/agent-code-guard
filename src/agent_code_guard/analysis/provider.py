"""Tree-sitter provider hidden behind a small cached parser boundary."""

from __future__ import annotations

from typing import Protocol

from .errors import ProviderUnavailableError


class ParserProvider(Protocol):
    def parse(self, language: str, source: bytes): ...


class TreeSitterProvider:
    """Load each embedded-language parser once per analysis provider."""

    def __init__(self, parser_factory=None) -> None:
        self._parsers: dict[str, object] = {}
        self._parser_factory = parser_factory

    @property
    def cached_languages(self) -> tuple[str, ...]:
        return tuple(self._parsers)

    def parse(self, language: str, source: bytes):
        parser = self._parsers.get(language)
        if parser is None:
            try:
                if self._parser_factory is None:
                    from tree_sitter_language_pack import get_parser
                    self._parser_factory = get_parser
                parser = self._parser_factory(language)
            except (ImportError, LookupError, OSError, RuntimeError) as exc:
                raise ProviderUnavailableError(
                    f"syntax provider unavailable for supported language {language!r}: {exc}; "
                    "reinstall Agent Code Guard"
                ) from exc
            self._parsers[language] = parser
        try:
            return parser.parse(source)
        except Exception as exc:
            raise ProviderUnavailableError(
                f"syntax provider failed for supported language {language!r}: {exc}; "
                "verify the Agent Code Guard installation"
            ) from exc
