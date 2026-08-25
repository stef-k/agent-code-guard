"""Strict version-1 persistence and lifecycle for the LOC legacy ratchet."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .file_selection import is_within
from .guards import loc
from .path_matching import matches_path_glob

RELATIVE_PATH = ".agent-tools/code-guard.loc-baseline.json"


def baseline_path(root: Path) -> Path:
    return root / RELATIVE_PATH


def load(path: Path) -> dict[str, int]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid LOC baseline: {exc}") from exc
    _exact_keys(document, {"version", "loc"}, "baseline")
    if isinstance(document.get("version"), bool) or document.get("version") != 1:
        raise ValueError("LOC baseline version must be the integer 1")
    loc_value = document.get("loc")
    _exact_keys(loc_value, {"files"}, "baseline.loc")
    files = loc_value.get("files")
    if not isinstance(files, list):
        raise ValueError("baseline.loc.files must be an array")
    result: dict[str, int] = {}
    stored_paths: list[str] = []
    for index, item in enumerate(files):
        location = f"baseline.loc.files[{index}]"
        _exact_keys(item, {"path", "allowedLoc"}, location)
        path = item.get("path")
        allowed = item.get("allowedLoc")
        if not isinstance(path, str) or not _canonical_path(path):
            raise ValueError(f"{location}.path must be a safe normalized relative path")
        if path in result:
            raise ValueError(f"duplicate LOC baseline path: {path}")
        if isinstance(allowed, bool) or not isinstance(allowed, int) or allowed <= 0:
            raise ValueError(f"{location}.allowedLoc must be a positive integer")
        result[path] = allowed
        stored_paths.append(path)
    if stored_paths != sorted(stored_paths):
        raise ValueError("LOC baseline entries must be sorted by path")
    return result


def load_if_present(root: Path) -> dict[str, int] | None:
    path = baseline_path(root)
    return load(path) if path.exists() else None


def validate_overlap(entries: dict[str, int], config: loc.Config) -> None:
    for path in entries:
        if any(matches_path_glob(path, item.path) for item in config.allowed_large_files):
            raise ValueError(f"LOC baseline path overlaps allowedLargeFiles: {path}")


def validate_paths(root: Path, entries: dict[str, int]) -> None:
    for relative in entries:
        candidate = root / Path(relative)
        resolved = candidate.resolve(strict=False)
        if not is_within(resolved, root):
            raise ValueError(f"LOC baseline path escapes analysis root: {relative}")
        current = root
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"LOC baseline path traverses a symlink: {relative}")


def create(root: Path, files: tuple[Path, ...], config: loc.Config) -> int:
    target = baseline_path(root)
    if target.exists():
        raise ValueError(f"LOC baseline already exists: {RELATIVE_PATH}")
    _require_enabled(config)
    entries: dict[str, int] = {}
    for path in files:
        _require_regular_inside(path, root)
        if not loc.should_include(path, config, root):
            continue
        relative = loc.relative_path(path, root)
        if any(matches_path_glob(relative, item.path) for item in config.allowed_large_files):
            continue
        counted = loc.count_loc(path, config)
        _, fail_at, _ = loc.effective_thresholds(relative, config)
        if counted > fail_at:
            entries[relative] = counted
    content = serialize(entries)
    created_directory = not target.parent.exists()
    try:
        target.parent.mkdir(exist_ok=True)
        _atomic_replace(target, content)
    except Exception:
        if created_directory:
            try:
                target.parent.rmdir()
            except OSError:
                pass
        raise
    return len(entries)


def update(
    root: Path, raw_bounds: list[str], invocation: Path, config: loc.Config,
    scope_excluded: tuple[Path, ...],
) -> tuple[int, int, int]:
    target = baseline_path(root)
    if not target.exists():
        raise ValueError(f"LOC baseline does not exist: {RELATIVE_PATH}")
    _require_enabled(config)
    entries = load(target)
    validate_paths(root, entries)
    validate_overlap(entries, config)
    bounds = _resolve_bounds(raw_bounds, invocation, root)
    proposed = dict(entries)
    excluded = {path.resolve() for path in scope_excluded}
    lowered = removed = unchanged = 0
    for relative, allowance in entries.items():
        if not _in_bounds(relative, bounds, root):
            continue
        path = root / Path(relative)
        if not path.exists():
            proposed.pop(relative)
            removed += 1
            continue
        _require_regular_inside(path, root)
        if path.resolve() in excluded or not loc.should_include(path, config, root):
            proposed.pop(relative)
            removed += 1
            continue
        counted = loc.count_loc(path, config)
        if counted > allowance:
            raise ValueError(
                f"LOC baseline update would increase allowance for {relative}: {allowance} to {counted}"
            )
        _, fail_at, _ = loc.effective_thresholds(relative, config)
        if counted <= fail_at:
            proposed.pop(relative)
            removed += 1
        elif counted < allowance:
            proposed[relative] = counted
            lowered += 1
        else:
            unchanged += 1
    content = serialize(proposed)
    if content != target.read_bytes():
        _atomic_replace(target, content)
    return lowered, removed, unchanged


def serialize(entries: dict[str, int]) -> bytes:
    document = {
        "version": 1,
        "loc": {"files": [
            {"path": path, "allowedLoc": entries[path]} for path in sorted(entries)
        ]},
    }
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_replace(target: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _resolve_bounds(values: list[str], invocation: Path, root: Path) -> list[tuple[Path, bool]]:
    bounds = []
    for value in values or ["."]:
        path = Path(value) if Path(value).is_absolute() else invocation / value
        if not path.exists():
            raise FileNotFoundError(f"explicit path does not exist: {value}")
        if path.is_symlink():
            raise ValueError(f"baseline bounds may not be symlinks: {value}")
        resolved = path.resolve()
        if not is_within(resolved, root):
            raise ValueError(f"baseline scope is outside analysis root: {value}")
        bounds.append((resolved, path.is_dir()))
    return bounds


def _in_bounds(relative: str, bounds: list[tuple[Path, bool]], root: Path) -> bool:
    candidate = (root / Path(relative)).resolve(strict=False)
    return any(
        is_within(candidate, bound) if is_directory else candidate == bound
        for bound, is_directory in bounds
    )


def _require_regular_inside(path: Path, root: Path) -> None:
    if path.is_symlink() or not path.is_file() or not is_within(path, root):
        raise ValueError(f"baseline scope contains an unsafe or outside-root path: {path}")


def _require_enabled(config: loc.Config) -> None:
    if not config.enabled:
        raise ValueError("LOC guard must be enabled for baseline writes")


def _exact_keys(value: Any, expected: set[str], location: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        if missing:
            raise ValueError(f"missing LOC baseline property: {location}.{missing[0]}")
        raise ValueError(f"unknown LOC baseline property: {location}.{unknown[0]}")


def _canonical_path(value: str) -> bool:
    if not value or "\\" in value or value.endswith("/") or "//" in value:
        return False
    path = Path(value)
    if path.is_absolute() or path.drive or value.startswith("//"):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))
