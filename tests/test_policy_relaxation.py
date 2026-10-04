"""Effective, bounded policy comparison without filesystem or syntax providers."""

from __future__ import annotations

import unittest

from agent_code_guard import callable_review_baseline
from agent_code_guard.config_validation import REVIEW_GUARD_NAMES
from agent_code_guard.guards import loc, policy_relaxation as policy
from agent_code_guard.result_model import required_policies


CONFIG_PATH = '.agent-tools/code-guard.config.json'


def config(name: str, **values) -> dict:
    """Build one persistent guard declaration for a comparator case."""
    return {'guards': {name: values}}


def comparison(before: dict, after: dict):
    return policy.compare(CONFIG_PATH, policy.effective_policy(before), policy.effective_policy(after))


class PolicyRelaxationTests(unittest.TestCase):
    def codes(self, result) -> list[str]:
        return [reason.reason_code for finding in result.findings for reason in finding.reasons]

    def test_enablement_and_review_threshold_matrix(self):
        defaults = dict(zip(REVIEW_GUARD_NAMES, (80, 4, 15, 800, 200)))
        for name in ('loc', *REVIEW_GUARD_NAMES):
            cases = [({}, config(name, enabled=False), ['guardDisabled']),
                     (config(name, enabled=False), {}, []), ({}, config(name, enabled=True), [])]
            if name != 'loc':
                threshold = defaults[name]
                cases.extend([
                    ({}, config(name, reviewAt=threshold + 1), ['thresholdIncreased']),
                    (config(name, reviewAt=threshold + 1), {}, []),
                    (config(name, reviewAt=threshold - 1), {}, ['thresholdIncreased']),
                    ({}, config(name, reviewAt=threshold), []),
                    (config(name, reviewAt=threshold), config(name, reviewAt=threshold - 1), []),
                ])
            for before, after, expected in cases:
                with self.subTest(name=name, before=before, after=after):
                    result = comparison(before, after)
                    self.assertEqual(self.codes(result), expected)
                    self.assertEqual(result.state, 'review' if expected else 'pass')
                    self.assertEqual(required_policies([result]), ['policyRelaxation'] if expected else [])

    def test_loc_scalar_matrix(self):
        cases = [
            ({}, {'warnAt': 450}, ['thresholdIncreased']),
            ({'warnAt': 350}, {}, ['thresholdIncreased']),
            ({'warnAt': 450}, {}, []),
            ({}, {'failAt': 650}, ['thresholdIncreased']),
            ({'failAt': 550}, {}, ['thresholdIncreased']),
            ({'failAt': 650}, {}, []),
            ({'ratchetAt': 'review'}, {}, ['ratchetModeWeakened']),
            ({}, {'ratchetAt': 'review'}, []),
            ({'countBlankLines': True}, {}, ['countedEvidenceReduced']),
            ({}, {'countBlankLines': True}, []),
            ({}, {'countCommentLines': False}, ['countedEvidenceReduced']),
            ({'countCommentLines': False}, {}, []),
            ({}, {'warnAt': 400, 'failAt': 600, 'ratchetAt': 'fail',
                  'countBlankLines': False, 'countCommentLines': True}, []),
        ]
        for before, after, expected in cases:
            with self.subTest(before=before, after=after):
                self.assertEqual(self.codes(comparison(config('loc', **before), config('loc', **after))), expected)

    def test_extension_coverage_uses_product_normalization_and_case(self):
        cases = [(['py', '.ts'], ['.py', '.ts', 'py'], []),
                 (['.py', '.ts'], ['.py'], ['extensionRemoved']),
                 (['.py'], ['.py', '.ts'], []),
                 (['.py'], ['.PY'], ['extensionRemoved']),
                 (None, sorted(loc.DEFAULT_INCLUDE_EXTENSIONS), [])]
        for before, after, expected in cases:
            with self.subTest(before=before, after=after):
                base = {} if before is None else config('loc', includeExtensions=before)
                self.assertEqual(self.codes(comparison(base, config('loc', includeExtensions=after))), expected)

    def test_exclusion_declarations_are_set_like_and_conservative(self):
        for surface in ('scope', 'loc'):
            def document(patterns):
                return {'scope': {'exclude': patterns}} if surface == 'scope' else config('loc', exclude=patterns)
            cases = [(['src/**'], ['src/**', 'src/generated/**'], ['exclusionAdded']),
                     (['src/**', 'tests/**'], ['tests/**', './src/**', 'src\\**'], []),
                     (['src/**'], [], []), ([], [], [])]
            for before, after, expected in cases:
                with self.subTest(surface=surface, before=before, after=after):
                    result = comparison(document(before), document(after))
                    self.assertEqual(self.codes(result), expected)
                    if expected:
                        self.assertIn('declaration added', result.findings[0].reasons[0].message)
        self.assertEqual(self.codes(comparison(config('loc', exclude=[]), {})),
                         ['exclusionAdded'] * len(loc.DEFAULT_EXCLUDES))

    def test_exemptions_ignore_reasons_order_and_equivalent_spelling(self):
        first = {'path': 'src/a.py', 'reason': 'reviewed'}
        second = {'path': 'src/b.py', 'reason': 'reviewed'}
        cases = [([], [first], ['exemptionAdded']), ([first], [], []),
                 ([first, second], [second, {'path': './src\\a.py', 'reason': 'new reason'}], []),
                 ([first], [first, first], [])]
        for before, after, expected in cases:
            with self.subTest(before=before, after=after):
                self.assertEqual(self.codes(comparison(config('loc', allowedLargeFiles=before),
                                                      config('loc', allowedLargeFiles=after))), expected)

    def test_ordered_override_topology_and_stable_thresholds(self):
        first = {'match': ['src/**', 'tests/**'], 'warnAt': 400, 'failAt': 600}
        second = {'match': ['other/**'], 'warnAt': 300, 'failAt': 500}
        cases = [([first], [{**first, 'match': ['tests/**', './src/**', 'src\\**']}], []),
                 ([first], [{**first, 'warnAt': 450, 'failAt': 650}], ['thresholdIncreased'] * 2),
                 ([first], [{**first, 'warnAt': 350, 'failAt': 550}], []),
                 ([first], [first], []), ([first], [], ['overrideTopologyChanged']),
                 ([], [first], ['overrideTopologyChanged']),
                 ([first, second], [second, first], ['overrideTopologyChanged']),
                 ([first], [{**first, 'match': ['new/**']}], ['overrideTopologyChanged'])]
        for before, after, expected in cases:
            with self.subTest(before=before, after=after):
                result = comparison(config('loc', overrides=before), config('loc', overrides=after))
                self.assertEqual(self.codes(result), expected)
                if expected == ['overrideTopologyChanged']:
                    self.assertIn('topology changed', result.findings[0].reasons[0].message)

    def test_three_baseline_families_compare_allowances_and_exact_callable_keys(self):
        entry = callable_review_baseline.Review('src/a.py', 'python', 'answer', 'callableSize', 90, 'accepted')
        for surface in ('loc_allowances', 'markdown_allowances', 'callable_reviews'):
            def snapshot(allowance, reason='accepted'):
                if surface == 'callable_reviews':
                    value = callable_review_baseline.Review(*entry.key, allowance, reason)
                    entries = {value.key: value} if allowance is not None else {}
                else:
                    entries = {'src/a.py' if surface == 'loc_allowances' else 'docs/a.md': allowance} if allowance is not None else {}
                return policy.effective_policy({}, **{surface: entries})
            for before, after, expected in [(None, 90, ['allowanceAdded']), (90, 91, ['allowanceIncreased']),
                                            (90, 89, []), (90, None, []), (90, 90, [])]:
                with self.subTest(surface=surface, before=before, after=after):
                    self.assertEqual(self.codes(policy.compare(CONFIG_PATH, snapshot(before), snapshot(after))), expected)
            self.assertEqual(self.codes(policy.compare(CONFIG_PATH, snapshot(90), snapshot(90, 'edited'))), [])
        other = callable_review_baseline.Review('src/a.py', 'python', 'answer', 'nesting', 5, 'accepted')
        result = policy.compare(CONFIG_PATH, policy.effective_policy({}, callable_reviews={entry.key: entry}),
                                policy.effective_policy({}, callable_reviews={other.key: other}))
        self.assertEqual(self.codes(result), ['allowanceAdded'])
        self.assertEqual(result.findings[0].reasons[0].to_json()['selector']['guard'], 'nesting')

    def test_mixed_changes_report_only_weakening_and_preserve_before_after(self):
        result = comparison(config('loc', warnAt=350, failAt=650), config('loc', warnAt=400, failAt=600))
        self.assertEqual(self.codes(result), ['thresholdIncreased'])
        reason = result.findings[0].reasons[0].to_json()
        self.assertEqual((reason['artifact'], reason['field'], reason['before'], reason['after']),
                         (CONFIG_PATH, 'guards.loc.warnAt', 350, 400))

    def test_large_aggregate_has_stable_order_counts_and_twenty_details(self):
        allowances = {f'src/{index:03}.py': 900 for index in range(35)}
        current = policy.effective_policy({'scope': {'exclude': ['z/**', 'a/**']}}, loc_allowances=allowances)
        reordered = policy.effective_policy({'scope': {'exclude': ['a/**', 'z/**']}},
                                            loc_allowances=dict(reversed(list(allowances.items()))))
        first = policy.compare(CONFIG_PATH, policy.effective_policy({}), current)
        self.assertEqual(first.to_json(), policy.compare(CONFIG_PATH, policy.effective_policy({}), reordered).to_json())
        finding = first.to_json()['findings'][0]
        self.assertEqual((finding['totalReasons'], len(finding['reasons']), finding['omittedReasons']), (37, 20, 17))
        self.assertEqual(finding['reasonCounts'], {'allowanceAdded': 35, 'exclusionAdded': 2})
        self.assertEqual(finding['artifactCounts'], {CONFIG_PATH: 2, '.agent-tools/code-guard.loc-baseline.json': 35})

