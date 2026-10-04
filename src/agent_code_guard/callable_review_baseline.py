"""Explicit reviewed ceilings for callable guards, independent of file baselines."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import baseline_files
from .file_selection import is_within
from .result_model import CallableFinding, GuardResult

if TYPE_CHECKING:
    from .analysis.facts import AnalysisFacts

RELATIVE_PATH = '.agent-tools/code-guard.callable-review-baseline.json'
# Configuration spelling is canonical in storage/CLI; result and policy IDs stay unchanged.
GUARD_IDS = {'callableSize': 'callableSize', 'nesting': 'nesting', 'cyclomaticComplexity': 'complexity'}
Selector = tuple[str, str, str]
ReviewKey = tuple[str, str, str, str]


@dataclass(frozen=True)
class Review:
    """A durable lexical selector and one human-reviewed guard ceiling."""

    path: str
    embedded_language: str
    callable: str
    guard: str
    allowed_measured: int
    reason: str

    @property
    def selector(self) -> Selector:
        return self.path, self.embedded_language, self.callable

    @property
    def key(self) -> ReviewKey:
        return *self.selector, self.guard

    def to_json(self) -> dict[str, Any]:
        return {
            'path': self.path, 'embeddedLanguage': self.embedded_language,
            'callable': self.callable, 'guard': self.guard,
            'allowedMeasured': self.allowed_measured, 'reason': self.reason,
        }


def baseline_path(root: Path) -> Path:
    return root / RELATIVE_PATH


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate callable review baseline property: {key}')
        result[key] = value
    return result


def _exact_keys(value: Any, keys: set[str], location: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f'{location} must have exactly these keys: {", ".join(sorted(keys))}')


def _text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError(f'callable review baseline {field} must be non-empty text')


def validate_guard(guard: str) -> None:
    """Reject aliases so a guard can never acquire two persisted identities."""
    if not isinstance(guard, str) or guard not in GUARD_IDS:
        raise ValueError('callable review baseline guard must be callableSize, nesting, or cyclomaticComplexity')


def load(path: Path) -> dict[ReviewKey, Review]:
    """Validate the independent schema without importing syntax providers."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'invalid callable review baseline: {exc}') from exc
    _exact_keys(data, {'version', 'callableReviews'}, 'callable review baseline')
    if type(data['version']) is not int or data['version'] != 1:
        raise ValueError('callable review baseline version must be the integer 1')
    if not isinstance(data['callableReviews'], list):
        raise ValueError('callable review baseline callableReviews must be an array')
    entries = {}
    for item in data['callableReviews']:
        _exact_keys(item, {'path', 'embeddedLanguage', 'callable', 'guard', 'allowedMeasured', 'reason'},
                    'callable review baseline entry')
        relative = item['path']
        if (not isinstance(relative, str) or not baseline_files.canonical_path(relative)
                or ':' in relative or '\x00' in relative):
            raise ValueError('callable review baseline path must be a safe normalized relative path')
        validate_guard(item['guard'])
        for field in ('embeddedLanguage', 'callable', 'reason'):
            _text(item[field], field)
        if type(item['allowedMeasured']) is not int or item['allowedMeasured'] <= 0:
            raise ValueError('callable review baseline allowedMeasured must be a positive integer')
        entry = Review(relative, item['embeddedLanguage'], item['callable'], item['guard'],
                       item['allowedMeasured'], item['reason'])
        if entry.key in entries:
            raise ValueError(f'duplicate callable review baseline entry: {entry.key}')
        entries[entry.key] = entry
    return entries


def _validate_storage(root: Path) -> None:
    target = baseline_path(root)
    if target.parent.is_symlink() or (target.parent.exists() and not target.parent.is_dir()):
        raise ValueError('callable review baseline directory must be a real directory inside the analysis root')
    if target.is_symlink() or not is_within(target.parent, root):
        raise ValueError('callable review baseline path must not traverse a symlink or escape the analysis root')


def load_if_present(root: Path) -> dict[ReviewKey, Review] | None:
    target = baseline_path(root)
    if not target.exists() and not target.is_symlink():
        return None
    _validate_storage(root)
    entries = load(target)
    baseline_files.validate_paths(root, {entry.path: 1 for entry in entries.values()}, 'callable review')
    return entries


def _current(
    root: Path, facts: AnalysisFacts, results: list[GuardResult],
) -> tuple[Counter[Selector], dict[ReviewKey, CallableFinding]]:
    """Index only runner-owned facts; range-qualified ownership remains in memory."""
    physical_paths = {
        facts.reporting_path_for(file.path, root): file.path.relative_to(root).as_posix()
        for file in facts.files
    }
    counts = Counter((fact.path.relative_to(root).as_posix(), fact.embedded_language, fact.identity)
                     for fact in facts.callables)
    canonical_ids = {result_id: guard for guard, result_id in GUARD_IDS.items()}
    findings = {}
    for result in results:
        if result.guard_id not in canonical_ids:
            continue
        for finding in result.findings:
            selector = (physical_paths[finding.path], finding.embedded_language, finding.callable)
            # Duplicates are deliberately absent from the usable finding index.
            if counts[selector] == 1:
                findings[(*selector, canonical_ids[result.guard_id])] = finding
    return counts, findings


def _require_unique(selector: Selector, counts: Counter[Selector]) -> None:
    if counts[selector] > 1:
        raise ValueError(f'ambiguous callable review: {selector}; remove the entry and re-review a unique identity')


def apply(
    root: Path, entries: dict[ReviewKey, Review], facts: AnalysisFacts, results: list[GuardResult],
) -> tuple[list[GuardResult], tuple[dict[str, str], ...]]:
    """Change acceptance only; preserve measurements, thresholds, and guard-native details."""
    counts, current = _current(root, facts, results)
    replacements = {}
    diagnostics = []
    analyzed_paths = {file.path.relative_to(root).as_posix() for file in facts.files}
    active_guards = {result.guard_id for result in results}
    for key, entry in sorted(entries.items()):
        if GUARD_IDS[entry.guard] not in active_guards:
            continue
        _require_unique(entry.selector, counts)
        finding = current.get(key)
        if finding is None:
            if entry.path in analyzed_paths:
                diagnostics.append({
                    'path': entry.path, 'embeddedLanguage': entry.embedded_language,
                    'callable': entry.callable, 'guard': entry.guard, 'status': 'stale',
                })
            continue
        threshold = finding.thresholds['reviewAt']
        status = ('notNeeded' if finding.measured <= threshold else
                  'withinAllowance' if finding.measured <= entry.allowed_measured else 'grown')
        replacements[id(finding)] = replace(
            finding, state='review' if status == 'grown' else 'pass',
            allowed_measured=entry.allowed_measured, ratchet_status=status, reason=entry.reason,
        )
    updated = []
    for result in results:
        if result.guard_id not in GUARD_IDS.values():
            updated.append(result)
            continue
        findings = [replacements.get(id(finding), finding) for finding in result.findings]
        updated.append(replace(result, findings=findings,
                               state='review' if any(item.state == 'review' for item in findings) else 'pass'))
    return updated, tuple(diagnostics)


def _write(root: Path, entries: dict[ReviewKey, Review], creating: bool) -> None:
    """Commit one fully validated proposal atomically, leaving no-op updates untouched."""
    _validate_storage(root)
    baseline_files.validate_paths(root, {entry.path: 1 for entry in entries.values()}, 'callable review')
    target = baseline_path(root)
    content = (json.dumps({'version': 1, 'callableReviews': [entries[key].to_json() for key in sorted(entries)]},
                          ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    created_directory = not target.parent.exists()
    try:
        target.parent.mkdir(exist_ok=True)
        if creating:
            baseline_files.atomic_create(target, content, 'callable review')
        elif content != target.read_bytes():
            baseline_files.atomic_replace(target, content)
    except Exception:
        if created_directory:
            try:
                target.parent.rmdir()
            except OSError:
                pass
        raise


def accept(
    root: Path, entries: dict[ReviewKey, Review] | None, facts: AnalysisFacts,
    results: list[GuardResult], path: Path, guard: str, language: str, callable: str, reason: str,
) -> None:
    """Record exactly one current REVIEW; existing ceilings cannot be replaced or raised."""
    validate_guard(guard)
    _text(language, 'embeddedLanguage')
    _text(callable, 'callable')
    _text(reason, 'reason')
    selector = (path.relative_to(root).as_posix(), language, callable)
    key = (*selector, guard)
    counts, current = _current(root, facts, results)
    _require_unique(selector, counts)
    if entries is not None and key in entries:
        raise ValueError('callable review allowance already exists; acceptance cannot replace or increase it')
    finding = current.get(key)
    if finding is None or finding.state != 'review':
        raise ValueError('acceptance target must be one current callable REVIEW in the explicit file')
    proposed = dict(entries or {})
    proposed[key] = Review(*selector, guard, finding.measured, reason.strip())
    _write(root, proposed, creating=entries is None)


def update(
    root: Path, entries: dict[ReviewKey, Review] | None, facts: AnalysisFacts,
    results: list[GuardResult], bounds: list[tuple[Path, bool]], prune_stale: bool,
) -> tuple[int, int, int, int]:
    """Lower/remove measured entries; prune missing identities only on explicit request."""
    if entries is None:
        raise ValueError(f'callable review baseline does not exist: {RELATIVE_PATH}')
    counts, current = _current(root, facts, results)
    analyzed_paths = {file.path.relative_to(root).as_posix() for file in facts.files}
    active_guards = {result.guard_id for result in results}
    proposed = dict(entries)
    lowered = removed = unchanged = stale = 0
    for key, entry in sorted(entries.items()):
        if not baseline_files.in_bounds(entry.path, bounds, root) or GUARD_IDS[entry.guard] not in active_guards:
            continue
        _require_unique(entry.selector, counts)
        finding = current.get(key)
        if finding is None:
            # An existing unselected/excluded/inapplicable file supplies no absence evidence.
            if entry.path not in analyzed_paths and (root / entry.path).exists():
                continue
            stale += 1
            if prune_stale:
                proposed.pop(key)
                removed += 1
            continue
        if finding.measured <= finding.thresholds['reviewAt']:
            proposed.pop(key)
            removed += 1
        elif finding.measured > entry.allowed_measured:
            raise ValueError(f'callable review baseline update would increase {entry.selector}: '
                             f'{entry.allowed_measured} to {finding.measured}')
        elif finding.measured < entry.allowed_measured:
            proposed[key] = replace(entry, allowed_measured=finding.measured)
            lowered += 1
        else:
            unchanged += 1
    if proposed != entries:
        _write(root, proposed, creating=False)
    return lowered, removed, unchanged, stale
