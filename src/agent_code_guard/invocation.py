"""Immutable runner-owned inputs shared by every guard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


JsonObject = Mapping[str, Any]


@dataclass(frozen=True, order=True)
class SelectedFile:
    """One canonical physical file and its stable public identity."""

    reporting_path: str
    physical_path: Path


@dataclass(frozen=True)
class AnalysisContext:
    """All immutable inputs established once at the runner boundary."""

    root: Path
    configuration: JsonObject
    selected_files: tuple[SelectedFile, ...]
    excluded_files: tuple[SelectedFile, ...] = ()


def load_configuration(config: str | None, start: Path) -> JsonObject:
    """Read one configuration document and recursively freeze it."""
    path = Path(config) if config else start / ".agent-tools" / "code-guard.config.json"
    if config and not path.exists():
        raise FileNotFoundError(f"config file not found: {config}")
    document = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(document, dict):
        raise ValueError("configuration must be an object")
    return _freeze(document)


def configuration_for_guard(args, document: JsonObject | None) -> JsonObject:
    """Compatibility seam for focused guard tests; production supplies the document."""
    return document if document is not None else load_configuration(args.config, Path.cwd())


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value
