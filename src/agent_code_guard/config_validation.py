"""Reject unsupported configuration properties before scope or guard work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT_KEYS = {"version", "scope", "guards"}
SCOPE_KEYS = {"exclude"}
GUARD_KEYS = {
    "loc",
    "callableSize",
    "nesting",
    "cyclomaticComplexity",
    "markdownDocumentSize",
    "markdownSectionSize",
}
REVIEW_GUARD_KEYS = {"enabled", "reviewAt"}
LOC_KEYS = {
    "enabled",
    "warnAt",
    "failAt",
    "countBlankLines",
    "countCommentLines",
    "includeExtensions",
    "exclude",
    "allowedLargeFiles",
    "overrides",
}
LOC_ALLOWED_LARGE_FILE_KEYS = {"path", "reason"}
LOC_OVERRIDE_KEYS = {"match", "warnAt", "failAt"}


def validate_configuration(config: str | None, start: Path) -> None:
    """Load the configured document once and validate its known property names."""
    path = Path(config) if config else start / ".agent-tools" / "code-guard.config.json"
    if config and not path.exists():
        raise FileNotFoundError(f"config file not found: {config}")
    if not path.exists():
        return
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("configuration must be an object")
    _reject_unknown(document, ROOT_KEYS, "")
    _validate_object_keys(document.get("scope"), SCOPE_KEYS, "scope")

    guards = document.get("guards")
    if not isinstance(guards, dict):
        return
    _reject_unknown(guards, GUARD_KEYS, "guards")
    for guard_name in GUARD_KEYS - {"loc"}:
        _validate_object_keys(guards.get(guard_name), REVIEW_GUARD_KEYS, f"guards.{guard_name}")
    loc = guards.get("loc")
    if not isinstance(loc, dict):
        return
    _reject_unknown(loc, LOC_KEYS, "guards.loc")
    _validate_items(
        loc.get("allowedLargeFiles"),
        LOC_ALLOWED_LARGE_FILE_KEYS,
        "guards.loc.allowedLargeFiles",
    )
    _validate_items(loc.get("overrides"), LOC_OVERRIDE_KEYS, "guards.loc.overrides")


def _validate_object_keys(value: Any, allowed: set[str], path: str) -> None:
    if isinstance(value, dict):
        _reject_unknown(value, allowed, path)


def _validate_items(value: Any, allowed: set[str], path: str) -> None:
    if not isinstance(value, list):
        return
    for index, item in enumerate(value):
        if isinstance(item, dict):
            _reject_unknown(item, allowed, f"{path}[{index}]")


def _reject_unknown(value: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(key for key in value if key not in allowed)
    if unknown:
        property_path = f"{path}.{unknown[0]}" if path else unknown[0]
        raise ValueError(f"unknown configuration property: {property_path}")
