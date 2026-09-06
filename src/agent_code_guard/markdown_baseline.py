"""Explicit, non-increasing allowances for reviewed Markdown documents."""

from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Any

from . import baseline_files
from .file_selection import is_within
from .guards.markdown_document_size import Config

RELATIVE_PATH = '.agent-tools/code-guard.markdown-baseline.json'


def baseline_path(root: Path) -> Path:
    return root / RELATIVE_PATH


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate Markdown baseline property: {key}')
        result[key] = value
    return result


def _exact_keys(value: Any, keys: set[str], location: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f'{location} must be an object with exactly these keys: {", ".join(sorted(keys))}')


def load(path: Path) -> dict[str, int]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'invalid Markdown baseline: {exc}') from exc
    _exact_keys(data, {'version', 'markdownDocumentSize'}, 'Markdown baseline')
    if type(data['version']) is not int or data['version'] != 1:
        raise ValueError('Markdown baseline version must be the integer 1')
    _exact_keys(data['markdownDocumentSize'], {'files'}, 'baseline.markdownDocumentSize')
    files = data['markdownDocumentSize']['files']
    if not isinstance(files, list):
        raise ValueError('baseline.markdownDocumentSize.files must be an array')
    entries = {}
    for item in files:
        _exact_keys(item, {'path', 'allowedLines'}, 'Markdown baseline entry')
        relative, allowance = item['path'], item['allowedLines']
        _validate_relative(relative)
        if relative in entries:
            raise ValueError(f'duplicate Markdown baseline path: {relative}')
        if type(allowance) is not int or allowance <= 0:
            raise ValueError('Markdown baseline allowedLines must be a positive integer')
        entries[relative] = allowance
    if list(entries) != sorted(entries):
        raise ValueError('Markdown baseline entries must be sorted by path')
    return entries


def _validate_relative(relative: Any) -> None:
    if (
        not isinstance(relative, str) or not baseline_files.canonical_path(relative)
        or PureWindowsPath(relative).drive or ':' in relative or '\x00' in relative
        or Path(relative).suffix.lower() != '.md'
    ):
        raise ValueError('Markdown baseline path must be a safe normalized relative .md path')


def _validate_storage(root: Path) -> None:
    target = baseline_path(root)
    directory = target.parent
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ValueError('Markdown baseline directory must be a real directory inside the analysis root')
    if target.is_symlink() or not is_within(directory, root):
        raise ValueError('Markdown baseline path must not traverse a symlink or escape the analysis root')


def load_if_present(root: Path) -> dict[str, int] | None:
    target = baseline_path(root)
    if not target.exists() and not target.is_symlink():
        return None
    _validate_storage(root)
    entries = load(target)
    baseline_files.validate_paths(root, entries, 'Markdown')
    return entries


def _require_enabled(config: Config) -> None:
    if not config.enabled:
        raise ValueError('Markdown document-size guard must be enabled for baseline writes')


def _measure(path: Path, root: Path) -> int:
    relative = path.relative_to(root).as_posix()
    _validate_relative(relative)
    baseline_files.validate_paths(root, {relative: 1}, 'Markdown')
    baseline_files.require_regular_inside(path, root)
    from .markdown import scan_text
    return scan_text(path, path.read_text(encoding='utf-8')).physical_lines


def _serialize(entries: dict[str, int]) -> bytes:
    data = {'version': 1, 'markdownDocumentSize': {'files': [
        {'path': path, 'allowedLines': entries[path]} for path in sorted(entries)
    ]}}
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def create(root: Path, files: tuple[Path, ...], config: Config) -> int:
    _require_enabled(config)
    _validate_storage(root)
    target = baseline_path(root)
    if target.exists():
        raise ValueError(f'Markdown baseline already exists: {RELATIVE_PATH}')
    entries = {}
    for path in files:
        if path.suffix.lower() == '.md':
            measured = _measure(path, root)
            if measured > config.review_at:
                entries[path.relative_to(root).as_posix()] = measured
    created_directory = not target.parent.exists()
    try:
        target.parent.mkdir(exist_ok=True)
        baseline_files.atomic_create(target, _serialize(entries), 'Markdown')
    except Exception:
        if created_directory:
            try:
                target.parent.rmdir()
            except OSError:
                pass
        raise
    return len(entries)


def update(
    root: Path, raw_bounds: list[str], invocation: Path, config: Config,
    scope_excluded: tuple[Path, ...],
) -> tuple[int, int, int]:
    _require_enabled(config)
    entries = load_if_present(root)
    if entries is None:
        raise ValueError(f'Markdown baseline does not exist: {RELATIVE_PATH}')
    bounds = baseline_files.resolve_bounds(raw_bounds, invocation, root)
    excluded = set(scope_excluded)
    proposed = dict(entries)
    lowered = removed = unchanged = 0
    for relative, allowance in entries.items():
        if not baseline_files.in_bounds(relative, bounds, root):
            continue
        path = root / relative
        if not path.exists() or path in excluded:
            proposed.pop(relative)
            removed += 1
            continue
        measured = _measure(path, root)
        if measured > allowance:
            raise ValueError(f'Markdown baseline update would increase allowance for {relative}: {allowance} to {measured}')
        if measured <= config.review_at:
            proposed.pop(relative)
            removed += 1
        elif measured < allowance:
            proposed[relative] = measured
            lowered += 1
        else:
            unchanged += 1
    target = baseline_path(root)
    content = _serialize(proposed)
    if content != target.read_bytes():
        baseline_files.atomic_replace(target, content)
    return lowered, removed, unchanged
