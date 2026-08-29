"""Resolve caller or Git scope before any guard applies its own filtering."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .invocation import AnalysisContext, JsonObject, SelectedFile
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
    excluded_files: tuple[Path, ...] = ()


def resolve_invocation(
    args: SelectionArgs, start: Path, configuration: JsonObject,
) -> AnalysisContext:
    """Resolve every physical/reporting identity once for one invocation."""
    scope = _resolve_scope(args, start, configuration)
    return AnalysisContext(
        scope.root,
        configuration,
        tuple(SelectedFile(_reporting_path(path, scope.root), path) for path in scope.files),
        tuple(SelectedFile(_reporting_path(path, scope.root), path) for path in scope.excluded_files),
    )


def find_repo_root(start: Path) -> Path | None:
    """Return the enclosing Git root, without inventing one when Git is absent."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=start, check=True,
            text=True, capture_output=True,
        )
        return _canonicalize(Path(result.stdout.strip()))
    except Exception:
        return None


def resolve_scope(args: SelectionArgs, start: Path) -> ResolvedScope:
    """Resolve and normalize the complete file scope shared by all guards."""
    from .invocation import load_configuration
    return _resolve_scope(args, start, load_configuration(getattr(args, "config", None), start))


def _resolve_scope(args: SelectionArgs, start: Path, configuration: JsonObject) -> ResolvedScope:
    working_root = _canonicalize(start)
    git_root = find_repo_root(working_root)
    root = git_root or working_root
    validate_selection_args(args, git_root)
    paths = resolve_explicit_paths(args.paths, working_root)

    if args.base_ref is not None:
        candidates = git_base_files(git_root, args.base_ref)
        files = bound_git_candidates(existing_files(candidates), paths)
    elif args.changed_only or args.staged:
        candidates = git_files(git_root, staged=args.staged)
        files = bound_git_candidates(existing_files(candidates), paths)
    else:
        files = existing_files(expand_paths(paths, git_root))

    normalized = tuple(dict.fromkeys(_canonicalize(path) for path in files))
    exclusions = load_scope_exclusions(args, configuration)
    identities = tuple((path, _reporting_path(path, root)) for path in normalized)
    excluded = tuple(
        path for path, reporting_path in identities
        if any(matches_path_glob(reporting_path, pattern) for pattern in exclusions)
    )
    excluded_set = set(excluded)
    return ResolvedScope(root, tuple(path for path in normalized if path not in excluded_set), excluded)


def _reporting_path(canonical_path: Path, canonical_root: Path) -> str:
    try:
        return canonical_path.relative_to(canonical_root).as_posix()
    except ValueError:
        return canonical_path.as_posix()


def resolve_explicit_paths(values: list[str], working_root: Path) -> list[Path]:
    """Resolve and validate positional paths against the caller's working directory."""
    paths = [Path(value) if Path(value).is_absolute() else working_root / value for value in values]
    missing = [value for value, path in zip(values, paths) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"explicit path does not exist: {missing[0]}")
    directory_links = [value for value, path in zip(values, paths) if path.is_symlink() and path.is_dir()]
    if directory_links:
        raise ValueError(
            f"explicit directory symlink is not recursively traversed: {directory_links[0]}"
        )
    return paths


def _canonicalize(path: Path) -> Path:
    """Owned filesystem identity seam; never call it from guard loops."""
    return path.resolve()


def bound_git_candidates(candidates: list[Path], bounds: list[Path]) -> list[Path]:
    """Intersect Git-selected files with the union of positional file/directory bounds."""
    normalized_bounds = [(path.resolve(), path.is_dir()) for path in bounds]
    return [
        candidate for candidate in candidates
        if any(
            is_within(candidate, bound) if is_directory else candidate.resolve() == bound
            for bound, is_directory in normalized_bounds
        )
    ]


def load_scope_exclusions(args: SelectionArgs, document: JsonObject) -> list[str]:
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
    return [path for path in selected if not path.is_symlink() and not has_pruned_directory(path, root)]


def walk_directory_files(directory: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dir_names, file_names in os.walk(directory):
        current = Path(current_root)
        dir_names[:] = sorted(
            name for name in dir_names
            if name not in BUILTIN_PRUNED_DIRECTORIES and not (current / name).is_symlink()
        )
        files.extend(
            current / name for name in sorted(file_names)
            if not (current / name).is_symlink()
        )
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
