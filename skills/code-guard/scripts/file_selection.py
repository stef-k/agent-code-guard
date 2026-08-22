"""Repository discovery and mature LOC file-selection semantics."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Protocol


class SelectionArgs(Protocol):
    paths: list[str]
    changed_only: bool
    staged: bool
    base_ref: str | None


def find_repo_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=start, check=True,
            text=True, capture_output=True,
        )
        return Path(result.stdout.strip()).resolve()
    except Exception:
        return start.resolve()


def validate_selection_args(args: SelectionArgs, root: Path) -> None:
    """Validate the runner-level scope independently of enabled guards."""
    has_base_ref = args.base_ref is not None
    if sum((args.changed_only, args.staged, has_base_ref)) > 1:
        raise ValueError("use only one file-selection mode: --changed-only, --staged, or --base-ref")
    if has_base_ref and not args.base_ref.strip():
        raise ValueError("--base-ref must not be empty")
    if has_base_ref:
        validate_base_ref(root, args.base_ref)


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


def collect_candidates(args: SelectionArgs, root: Path) -> list[Path]:
    has_base_ref = args.base_ref is not None
    if has_base_ref:
        return git_base_files(root, args.base_ref)
    if args.changed_only or args.staged:
        return git_files(root, staged=args.staged)
    return expand_paths([Path(path) for path in args.paths])


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
                files.extend(Path(current_root) / name for name in file_names)
    return files
