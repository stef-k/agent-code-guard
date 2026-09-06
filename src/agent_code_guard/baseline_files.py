"""Filesystem safety shared by explicit source-controlled baseline workflows."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .file_selection import is_within


def validate_paths(root: Path, entries: dict[str, int], label: str = "LOC") -> None:
    for relative in entries:
        candidate = root / Path(relative)
        resolved = candidate.resolve(strict=False)
        if not is_within(resolved, root):
            raise ValueError(f"{label} baseline path escapes analysis root: {relative}")
        current = root
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"{label} baseline path traverses a symlink: {relative}")


def validate_explicit_scope(
    values: list[str], invocation: Path, root: Path, selected_files: tuple[Path, ...],
) -> set[Path]:
    """Validate raw bounds before resolution erases empty directories and file-link identity."""
    linked_targets: set[Path] = set()
    directly_reached: set[Path] = set()
    for value in values or ["."]:
        path = Path(value) if Path(value).is_absolute() else invocation / value
        resolved = path.resolve()
        if not is_within(resolved, root):
            raise ValueError(f"baseline scope is outside analysis root: {value}")
        if path.is_symlink() and path.is_file():
            linked_targets.add(resolved)
        elif path.is_file():
            directly_reached.add(resolved)
        elif path.is_dir():
            directly_reached.update(
                selected.resolve() for selected in selected_files if is_within(selected, resolved)
            )
    return linked_targets - directly_reached


def atomic_replace(target: Path, content: bytes) -> None:
    temporary = _write_temporary(target, content)
    try:
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_create(target: Path, content: bytes, label: str = "LOC") -> None:
    temporary = _write_temporary(target, content)
    try:
        os.link(temporary, target)
    except FileExistsError as exc:
        raise ValueError(f"{label} baseline already exists: {target.parent.name}/{target.name}") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_temporary(target: Path, content: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def resolve_bounds(values: list[str], invocation: Path, root: Path) -> list[tuple[Path, bool]]:
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


def in_bounds(relative: str, bounds: list[tuple[Path, bool]], root: Path) -> bool:
    candidate = (root / Path(relative)).resolve(strict=False)
    return any(
        is_within(candidate, bound) if is_directory else candidate == bound
        for bound, is_directory in bounds
    )


def require_regular_inside(path: Path, root: Path) -> None:
    if path.is_symlink() or not path.is_file() or not is_within(path, root):
        raise ValueError(f"baseline scope contains an unsafe or outside-root path: {path}")


def canonical_path(value: str) -> bool:
    if not value or "\\" in value or value.endswith("/") or "//" in value:
        return False
    path = Path(value)
    if path.is_absolute() or path.drive or value.startswith("//"):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def validate_analysis_scope(root: Path, files: tuple[Path, ...]) -> None:
    """Recheck physical containment before applying any persisted allowance."""
    error = "baseline analysis scope is outside analysis root"
    try:
        current_root = root.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{error}: {root}") from exc
    for path in files:
        try:
            current_path = path.resolve(strict=True)
            valid = (
                not path.is_symlink() and current_path.is_file()
                and current_path.is_relative_to(current_root)
            )
        except OSError:
            valid = False
        if not valid:
            raise ValueError(f"{error}: {path}")
