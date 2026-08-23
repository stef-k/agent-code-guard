"""Shared normalized path matching for common scope and guard policies."""

from __future__ import annotations

import fnmatch
from pathlib import Path


def matches_path_glob(path: str, pattern: str) -> bool:
    normalised_path = path.replace("\\", "/").removeprefix("./")
    normalised_pattern = pattern.replace("\\", "/").removeprefix("./")
    if normalised_path == normalised_pattern:
        return True
    candidates = [normalised_pattern]
    while normalised_pattern.startswith("**/"):
        normalised_pattern = normalised_pattern[3:]
        candidates.append(normalised_pattern)
    return any(fnmatch.fnmatch(normalised_path, candidate) for candidate in candidates)


def relative_or_absolute_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
