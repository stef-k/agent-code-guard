"""Resolve caller or Git scope before any guard applies its own filtering."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .path_matching import matches_path_glob, relative_or_absolute_path

BUILTIN_PRUNED_DIRECTORIES = {".git", "node_modules", "bin", "obj"}


class SelectionArgs(Protocol):
    paths: list[str]
    changed_only: bool
    staged: bool
    base_ref: str | None
    config: str | None
    scope_exclude: list[str]


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
        files = existing_files(expand_paths(paths, git_root))

    normalized = tuple(dict.fromkeys(path.resolve() for path in files))
    exclusions = load_scope_exclusions(args, working_root)
    filtered = tuple(
        path for path in normalized
        if not any(matches_path_glob(relative_or_absolute_path(path, root), pattern) for pattern in exclusions)
    )
    return ResolvedScope(root, filtered)


def load_scope_exclusions(args: SelectionArgs, start: Path) -> list[str]:
    explicit_config = getattr(args, "config", None)
    config_path = Path(explicit_config) if explicit_config else start / ".agent-tools" / "code-guard.config.json"
    if explicit_config and not config_path.exists():
        raise FileNotFoundError(f"config file not found: {explicit_config}")
    document = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    if not isinstance(document, dict):
        raise ValueError("configuration must be an object")
    scope = document.get("scope", {})
    if not isinstance(scope, dict):
        raise ValueError("scope must be an object")
    exclude = scope.get("exclude", [])
    if not isinstance(exclude, list) or any(not isinstance(pattern, str) for pattern in exclude):
        raise ValueError("scope.exclude must be an array of strings")
    combined = [*exclude, *getattr(args, "scope_exclude", [])]
    if any(not isinstance(pattern, str) or not pattern.strip() for pattern in combined):
        raise ValueError("scope.exclude patterns must be non-empty strings")
    return combined


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


def expand_paths(paths: list[Path], git_root: Path | None) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            if git_root is not None and is_within(path, git_root):
                files.extend(git_directory_files(git_root, path))
            else:
                files.extend(walk_directory_files(path))
    return files


def git_directory_files(root: Path, directory: Path) -> list[Path]:
    relative = directory.resolve().relative_to(root.resolve())
    pathspec = "." if not relative.parts else relative.as_posix()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", pathspec],
        cwd=root, check=True, capture_output=True,
    )
    selected = [root / os.fsdecode(value) for value in result.stdout.split(b"\0") if value]
    return [path for path in selected if not has_pruned_directory(path, root)]


def walk_directory_files(directory: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dir_names, file_names in os.walk(directory):
        dir_names[:] = sorted(name for name in dir_names if name not in BUILTIN_PRUNED_DIRECTORIES)
        files.extend(Path(current_root) / name for name in sorted(file_names))
    return files


def has_pruned_directory(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(part in BUILTIN_PRUNED_DIRECTORIES for part in relative.parts[:-1])


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def existing_files(paths: list[Path]) -> list[Path]:
    """Ignore absent Git-derived entries while retaining every existing artifact."""
    return [path for path in paths if path.exists() and path.is_file()]
