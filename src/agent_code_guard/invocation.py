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
class GitAuthority:
    """Resolved commit objects shared by source selection and policy comparison."""

    head_object: str | None
    base_object: str | None


@dataclass(frozen=True)
class LoadedConfiguration:
    """The active invocation-relative artifact and its frozen parsed document."""

    path: Path
    document: JsonObject


@dataclass(frozen=True)
class AnalysisContext:
    """All immutable inputs established once at the runner boundary."""

    root: Path
    configuration: JsonObject
    selected_files: tuple[SelectedFile, ...]
    excluded_files: tuple[SelectedFile, ...] = ()
    configuration_path: Path | None = None
    git_authority: GitAuthority | None = None


def load_configuration(config: str | None, start: Path) -> JsonObject:
    """Read one configuration document and recursively freeze it."""
    return load_active_configuration(config, start).document


def configuration_path(config: str | None, start: Path) -> Path:
    """Retain the actual path without erasing symlink ownership information."""
    path = Path(config) if config else Path('.agent-tools/code-guard.config.json')
    return path if path.is_absolute() else start / path


def load_active_configuration(config: str | None, start: Path) -> LoadedConfiguration:
    """Load once and retain the artifact whose policy governs this invocation."""
    path = configuration_path(config, start)
    if config and not path.exists():
        raise FileNotFoundError(f"config file not found: {config}")
    text = path.read_text(encoding="utf-8") if path.exists() else '{}'
    return LoadedConfiguration(path, parse_configuration(text))


def parse_configuration(text: str) -> JsonObject:
    """Parse and freeze current or historical text with the same property validation."""
    from .config_validation import validate_configuration
    document = json.loads(text)
    if not isinstance(document, dict):
        raise ValueError("configuration must be an object")
    frozen = _freeze(document)
    validate_configuration(None, Path('.'), frozen)
    return frozen


def configuration_for_guard(args, document: JsonObject | None) -> JsonObject:
    """Compatibility seam for focused guard tests; production supplies the document."""
    return document if document is not None else load_configuration(args.config, Path.cwd())


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value
