"""Resolve caller or Git scope before any guard applies its own filtering."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class SelectionArgs(Protocol):
    paths: list[str]
    changed_only: bool
    staged: bool
    base_ref: str | None


@dataclass(frozen=True)
class ResolvedScope:
    root: Path
    files: tuple[Path, ...]


def find_repo_root(start: Path) -> Path | None:
    """Return the enclosing Git root, without inventing one when Git is absent."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=start, check=True,
            text=True, capture_output=True,
        )
        return Path(result.stdout.strip()).resolve()
    except Exception:
        return None


def resolve_scope(args: SelectionArgs, start: Path) -> ResolvedScope:
    """Resolve and normalize the complete file scope shared by all guards."""
    working_root = start.resolve()
    git_root = find_repo_root(working_root)
    root = git_root or working_root
    validate_selection_args(args, git_root)

    if args.base_ref is not None:
        candidates = git_base_files(git_root, args.base_ref)
        files = existing_files(candidates)
    elif args.changed_only or args.staged:
        candidates = git_files(git_root, staged=args.staged)
        files = existing_files(candidates)
    else:
        paths = [Path(value) if Path(value).is_absolute() else working_root / value for value in args.paths]
        missing = [value for value, path in zip(args.paths, paths) if not path.exists()]
        if missing:
            raise FileNotFoundError(f"explicit path does not exist: {missing[0]}")
        files = existing_files(expand_paths(paths))

    return ResolvedScope(root, tuple(dict.fromkeys(path.resolve() for path in files)))


def validate_selection_args(args: SelectionArgs, git_root: Path | None) -> None:
    """Validate the runner-level scope independently of enabled guards."""
    has_base_ref = args.base_ref is not None
    if sum((args.changed_only, args.staged, has_base_ref)) > 1:
        raise ValueError("use only one file-selection mode: --changed-only, --staged, or --base-ref")
    if has_base_ref and not args.base_ref.strip():
        raise ValueError("--base-ref must not be empty")
    if (args.changed_only or args.staged or has_base_ref) and git_root is None:
        raise RuntimeError("Git file-selection mode requires a Git repository")
    if has_base_ref:
        validate_base_ref(git_root, args.base_ref)


def validate_base_ref(root: Path, base_ref: str) -> None:
    try:
        subprocess.run(
            ["git", "merge-base", base_ref, "HEAD"], cwd=root, check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = os.fsdecode(exc.stderr).strip()
        message = f"unable to compare base ref {base_ref!r} with HEAD"
        raise RuntimeError(f"{message}: {detail}" if detail else message) from exc


def git_files(root: Path, staged: bool) -> list[Path]:
    has_head = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=root,
        check=False, capture_output=True,
    ).returncode == 0
    diff_target = ["--cached"] if staged or not has_head else ["HEAD"]
    result = subprocess.run(
        ["git", "diff", *diff_target, "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=root, check=True, capture_output=True,
    )
    files = [root / os.fsdecode(path) for path in result.stdout.split(b"\0") if path]
    if not staged:
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=root, check=True, capture_output=True,
        )
        files.extend(root / os.fsdecode(path) for path in untracked.stdout.split(b"\0") if path)
    return files


def git_base_files(root: Path, base_ref: str) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "-z", f"{base_ref}...HEAD", "--"],
            cwd=root, check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = os.fsdecode(exc.stderr).strip()
        message = f"unable to compare base ref {base_ref!r} with HEAD"
        raise RuntimeError(f"{message}: {detail}" if detail else message) from exc
    return [root / os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def expand_paths(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for current_root, dir_names, file_names in os.walk(path):
                dir_names[:] = [name for name in dir_names if name not in {".git", "node_modules", "bin", "obj"}]
                dir_names.sort()
                files.extend(Path(current_root) / name for name in sorted(file_names))
    return files


def existing_files(paths: list[Path]) -> list[Path]:
    """Ignore absent Git-derived entries while retaining every existing artifact."""
    return [path for path in paths if path.exists() and path.is_file()]
