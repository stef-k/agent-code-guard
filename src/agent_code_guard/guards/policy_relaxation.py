"""Bounded comparison of the persistent policy surfaces admitted by issue #136."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from types import SimpleNamespace

from . import callable_size, complexity, loc, markdown_document_size, markdown_section_size, nesting
from .. import callable_review_baseline, loc_baseline, markdown_baseline
from ..config_validation import validate_configuration
from ..file_selection import load_scope_exclusions
from ..invocation import JsonObject
from ..result_model import GuardResult, PolicyReason, PolicyRelaxationFinding

DETAIL_LIMIT = 20
REVIEW_GUARDS = (
    ('callableSize', callable_size), ('nesting', nesting), ('cyclomaticComplexity', complexity),
    ('markdownDocumentSize', markdown_document_size), ('markdownSectionSize', markdown_section_size),
)
MESSAGES = {
    'guardDisabled': 'Guard changed from enabled to disabled.',
    'thresholdIncreased': 'Effective threshold increased.',
    'ratchetModeWeakened': 'LOC ratchet changed from REVIEW-level to FAIL-level adoption.',
    'countedEvidenceReduced': 'LOC counting changed from including to ignoring these lines.',
    'extensionRemoved': 'Covered LOC extension removed.',
    'exclusionAdded': 'Exclusion declaration added; smaller effective path coverage is not proven.',
    'exemptionAdded': 'LOC exemption path declaration added; authorization is outside this comparison.',
    'overrideTopologyChanged': 'Ordered LOC override match topology changed; path-specific weakening is not proven.',
    'allowanceAdded': 'Persisted allowance entry added; authorization is outside this comparison.',
    'allowanceIncreased': 'Persisted numeric allowance increased.',
}


@dataclass(frozen=True)
class EffectivePolicy:
    """Exactly the configured controls and three baseline families being compared."""

    loc: loc.Config
    reviews: tuple[tuple[str, bool, int | None], ...]
    scope_exclusions: frozenset[str]
    loc_allowances: Mapping[str, int]
    markdown_allowances: Mapping[str, int]
    callable_reviews: Mapping[callable_review_baseline.ReviewKey, callable_review_baseline.Review]


def effective_policy(
    document: JsonObject, loc_allowances: Mapping[str, int] | None = None,
    markdown_allowances: Mapping[str, int] | None = None,
    callable_reviews: Mapping[callable_review_baseline.ReviewKey, callable_review_baseline.Review] | None = None,
) -> EffectivePolicy:
    """Use production loaders/defaults with neutral CLI choices; perform no I/O."""
    args = SimpleNamespace(warn=None, fail=None, include=[], exclude=[], scope_exclude=[],
                           count_blank_lines=False, ignore_comment_lines=False)
    validate_configuration(None, None, document)
    reviews = []
    for name, guard in REVIEW_GUARDS:
        configuration = guard.load_config(args, document)
        reviews.append((name, configuration.enabled, configuration.review_at))
    return EffectivePolicy(
        loc.load_config(args, document), tuple(reviews),
        _declarations(load_scope_exclusions(args, document)),
        loc_allowances or {}, markdown_allowances or {}, callable_reviews or {},
    )


def compare(artifact: str, before: EffectivePolicy, after: EffectivePolicy) -> GuardResult:
    """Report admitted weakening and conservative changes without a net score."""
    reasons = list(_configuration_reasons(artifact, before, after))
    reasons.extend(_allowance_reasons(loc_baseline.RELATIVE_PATH, 'allowedLoc',
                                     before.loc_allowances, after.loc_allowances))
    reasons.extend(_allowance_reasons(markdown_baseline.RELATIVE_PATH, 'allowedLines',
                                     before.markdown_allowances, after.markdown_allowances))
    reasons.extend(_callable_reasons(before.callable_reviews, after.callable_reviews))
    if not reasons:
        return GuardResult('policyRelaxation', 'pass', [])
    reasons.sort(key=PolicyReason.sort_key)
    finding = PolicyRelaxationFinding(
        len(reasons), dict(sorted(Counter(reason.reason_code for reason in reasons).items())),
        dict(sorted(Counter(reason.artifact for reason in reasons).items())),
        tuple(reasons[:DETAIL_LIMIT]), max(0, len(reasons) - DETAIL_LIMIT),
    )
    return GuardResult('policyRelaxation', 'review', [finding])


def _reason(artifact, field, code, before, after, *, path=None, selector=None) -> PolicyReason:
    return PolicyReason(artifact, field, code, before, after, MESSAGES[code], path, selector)


def _configuration_reasons(artifact: str, before: EffectivePolicy, after: EffectivePolicy):
    """Compare active guard settings; common scope is independent of enablement."""
    old, new = before.loc, after.loc
    if old.enabled and not new.enabled:
        yield _reason(artifact, 'guards.loc.enabled', 'guardDisabled', True, False)
    for (name, enabled, threshold), (_, current_enabled, current_threshold) in zip(before.reviews, after.reviews):
        if enabled and not current_enabled:
            yield _reason(artifact, f'guards.{name}.enabled', 'guardDisabled', True, False)
        if enabled and current_enabled and current_threshold > threshold:
            yield _reason(artifact, f'guards.{name}.reviewAt', 'thresholdIncreased', threshold, current_threshold)
    yield from _added_declarations(artifact, 'scope.exclude', before.scope_exclusions, after.scope_exclusions)
    if not (old.enabled and new.enabled):
        return
    for field, previous, current in (('warnAt', old.warn_at, new.warn_at), ('failAt', old.fail_at, new.fail_at)):
        if current > previous:
            yield _reason(artifact, f'guards.loc.{field}', 'thresholdIncreased', previous, current)
    if old.ratchet_at == 'review' and new.ratchet_at == 'fail':
        yield _reason(artifact, 'guards.loc.ratchetAt', 'ratchetModeWeakened', 'review', 'fail')
    for field, previous, current in (('countBlankLines', old.count_blank_lines, new.count_blank_lines),
                                     ('countCommentLines', old.count_comment_lines, new.count_comment_lines)):
        if previous and not current:
            yield _reason(artifact, f'guards.loc.{field}', 'countedEvidenceReduced', True, False)
    for extension in old.include_extensions - new.include_extensions:
        yield _reason(artifact, 'guards.loc.includeExtensions', 'extensionRemoved', True, False, path=extension)
    yield from _added_declarations(artifact, 'guards.loc.exclude', _declarations(old.exclude), _declarations(new.exclude))
    yield from _added_declarations(artifact, 'guards.loc.allowedLargeFiles',
                                  _declarations(item.path for item in old.allowed_large_files),
                                  _declarations(item.path for item in new.allowed_large_files), 'exemptionAdded')
    yield from _override_reasons(artifact, old.overrides, new.overrides)


def _declarations(values) -> frozenset[str]:
    """Mirror production path spelling only; do not infer glob equivalence."""
    return frozenset(value.replace('\\', '/').removeprefix('./') for value in values)


def _added_declarations(artifact, field, before, after, code='exclusionAdded'):
    for declaration in after - before:
        yield _reason(artifact, field, code, False, True, path=declaration)


def _override_reasons(artifact, before: list[loc.ThresholdOverride], after: list[loc.ThresholdOverride]):
    """Compare thresholds only when ordered normalized match sets are unchanged."""
    old_topology = tuple(tuple(sorted(_declarations(item.match))) for item in before)
    new_topology = tuple(tuple(sorted(_declarations(item.match))) for item in after)
    if old_topology != new_topology:
        yield _reason(artifact, 'guards.loc.overrides', 'overrideTopologyChanged',
                      _topology_summary(old_topology), _topology_summary(new_topology))
        return
    for index, (old, new) in enumerate(zip(before, after)):
        for field, previous, current in (('warnAt', old.warn_at, new.warn_at), ('failAt', old.fail_at, new.fail_at)):
            if current > previous:
                yield _reason(artifact, f'guards.loc.overrides[{index}].{field}', 'thresholdIncreased', previous, current)


def _topology_summary(topology: tuple) -> dict[str, object]:
    """Keep even one very large topology change bounded, with an exact fingerprint."""
    encoded = json.dumps(topology, ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    return {'entries': len(topology), 'sha256': hashlib.sha256(encoded).hexdigest()}


def _allowance_reasons(artifact, field, before: Mapping[str, int], after: Mapping[str, int]):
    for path, allowance in after.items():
        previous = before.get(path)
        if previous is None or allowance > previous:
            code = 'allowanceAdded' if previous is None else 'allowanceIncreased'
            yield _reason(artifact, field, code, previous, allowance, path=path)


def _callable_reasons(before, after):
    for key, entry in after.items():
        previous = before[key].allowed_measured if key in before else None
        if previous is None or entry.allowed_measured > previous:
            code = 'allowanceAdded' if previous is None else 'allowanceIncreased'
            yield _reason(callable_review_baseline.RELATIVE_PATH, 'allowedMeasured', code,
                          previous, entry.allowed_measured, selector=key)
