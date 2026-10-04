"""Callable-review schema, durable identity, and shared guard behavior."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase


BASELINE = Path('.agent-tools/code-guard.callable-review-baseline.json')
GUARDS = {'callableSize': 'callableSize', 'nesting': 'nesting', 'cyclomaticComplexity': 'complexity'}
REASON = 'Reviewed cohesive transaction; re-review on growth.'


def review(guard='cyclomaticComplexity', measured=4, **changes):
    """One explicit reviewed selector, without persisted coordinates."""
    return {
        'path': 'sample.py', 'embeddedLanguage': 'python', 'callable': 'sample.selected',
        'guard': guard, 'allowedMeasured': measured, 'reason': REASON, **changes,
    }


def store(root, entries):
    """Write source-controlled test input, not an acceptance operation."""
    path = root / BASELINE
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'version': 1, 'callableReviews': entries}), encoding='utf-8')
    return path


def configure(root, guard='cyclomaticComplexity', threshold=2, **changes):
    """Isolate one callable guard while retaining runner-owned selection."""
    guards = {name: {'enabled': False} for name in (
        'loc', *GUARDS, 'markdownDocumentSize', 'markdownSectionSize',
    )}
    guards[guard] = {'reviewAt': threshold}
    path = root / '.agent-tools/code-guard.config.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'version': 1, 'guards': guards, **changes}), encoding='utf-8')


def source(guard, measured, name='selected'):
    """Small real callables whose guard-native measurements are explicit."""
    lines = [f'def {name}(value):\n']
    if guard == 'callableSize':
        lines.extend('    value += 1\n' for _ in range(measured - 2))
    elif guard == 'nesting':
        lines.extend('    ' * (depth + 1) + 'if value:\n' for depth in range(measured))
        lines.append('    ' * (measured + 1) + 'value += 1\n')
    else:
        lines.extend('    if value:\n        value += 1\n' for _ in range(measured - 1))
    return ''.join(lines) + '    return value\n'


class CallableReviewBaselineTests(CodeGuardTestCase):
    def test_each_guard_uses_the_same_non_increasing_ratchet(self):
        for guard, result_id in GUARDS.items():
            threshold = 3 if guard == 'callableSize' else 2
            accepted = threshold + 2
            with self.subTest(guard=guard), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                configure(root, guard, threshold)
                path = root / 'sample.py'
                path.write_text(source(guard, accepted), encoding='utf-8')
                ordinary = self.read_json(self.run_guard(root, 'sample.py', '--json'))
                finding = ordinary['guards'][result_id]['findings'][0]
                self.assertEqual((finding['state'], finding['measured']), ('review', accepted))
                self.assertNotIn('allowedMeasured', finding)
                baseline = store(root, [review(guard, accepted)])
                before = baseline.read_bytes()
                for measured, status, state in (
                    (accepted, 'withinAllowance', 'pass'),
                    (accepted - 1, 'withinAllowance', 'pass'),
                    (accepted + 1, 'grown', 'review'),
                    (threshold, 'notNeeded', 'pass'),
                ):
                    with self.subTest(measured=measured):
                        path.write_text(source(guard, measured), encoding='utf-8')
                        result = self.run_guard(root, 'sample.py', '--json')
                        data = self.read_json(result)
                        finding = data['guards'][result_id]['findings'][0]
                        self.assertEqual((finding['measured'], finding['state']), (measured, state))
                        self.assertEqual(finding['thresholds'], {'reviewAt': threshold})
                        self.assertEqual((finding['allowedMeasured'], finding['ratchetStatus'], finding['reason']),
                                         (accepted, status, REASON))
                        self.assertEqual(result.returncode, int(state == 'review'))
                        self.assertEqual(data['requiredPolicies'], [result_id] if state == 'review' else [])
                        self.assertEqual(baseline.read_bytes(), before)
                path.write_text(source(guard, accepted) + source(guard, accepted, 'unrelated'), encoding='utf-8')
                data = self.read_json(self.run_guard(root, 'sample.py', '--json'))
                self.assertEqual([item['state'] for item in data['guards'][result_id]['findings']], ['pass', 'review'])

    def test_named_identity_survives_lines_but_rename_and_move_are_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            path = root / 'sample.py'
            path.write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            store(root, [review()])
            path.write_text('# Unrelated\n\n' + source('cyclomaticComplexity', 4), encoding='utf-8')
            result = self.run_guard(root, 'sample.py', '--json')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.read_json(result)['guards']['complexity']['findings'][0]['range']['startLine'], 3)
            path.write_text(source('cyclomaticComplexity', 4, 'renamed'), encoding='utf-8')
            renamed = self.read_json(self.run_guard(root, 'sample.py', '--json'))
            self.assertEqual(renamed['guards']['complexity']['state'], 'review')
            self.assertEqual(renamed['callableReviewBaseline']['diagnostics'][0]['status'], 'stale')
            (root / 'moved').mkdir()
            path.rename(root / 'moved/sample.py')
            moved = self.read_json(self.run_guard(root, 'moved/sample.py', '--json'))
            self.assertEqual(moved['guards']['complexity']['state'], 'review')
            self.assertNotIn('allowedMeasured', moved['guards']['complexity']['findings'][0])

    def test_duplicate_lexical_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            (root / 'sample.py').write_text(source('cyclomaticComplexity', 4) * 2, encoding='utf-8')
            baseline = store(root, [review()])
            before = baseline.read_bytes()
            result = self.run_guard(root, 'sample.py', '--json')
            self.assertEqual(result.returncode, 3)
            self.assertIn('ambiguous callable review', self.read_json(result)['error'])
            self.assertEqual(baseline.read_bytes(), before)

    def test_malformed_baseline_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            (root / 'sample.py').write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            invalid_entries = [
                [review(), review()], [review(guard='complexity')], [review(guard='unknown')],
                [review(extra=True)], [review(startLine=1)],
            ]
            invalid_entries.extend([review(path=path)] for path in (
                '../sample.py', '/sample.py', 'C:/sample.py', './sample.py',
                'a//sample.py', 'a\\sample.py', 'sample.py/', 'sample\x00.py',
            ))
            invalid_entries.extend([review(allowedMeasured=value)] for value in (True, 0, -1, 4.0, '4', {}, None))
            invalid_entries.extend([review(**{field: value})] for field in ('reason', 'callable', 'embeddedLanguage')
                                   for value in ('', '  ', None, 1))
            documents = [{'version': 1, 'callableReviews': entries} for entries in invalid_entries]
            documents.extend(({'version': version, 'callableReviews': []} for version in (True, 1.0, 2, '1')))
            documents.extend(({'version': 1, 'callableReviews': {}}, {'version': 1},
                              {'version': 1, 'callableReviews': [], 'unknown': True}))
            baseline = root / BASELINE
            for document in documents:
                with self.subTest(document=document):
                    baseline.write_text(json.dumps(document), encoding='utf-8')
                    before = baseline.read_bytes()
                    result = self.run_guard(root, 'sample.py', '--json')
                    self.assertEqual(result.returncode, 3, result.stdout)
                    self.assertIn('baseline', self.read_json(result)['error'])
                    self.assertEqual(baseline.read_bytes(), before)
            for content in ('{', '{"version":1,"version":1,"callableReviews":[]}'):
                baseline.write_text(content, encoding='utf-8')
                self.assertEqual(self.run_guard(root, 'sample.py', '--json').returncode, 3)

    def test_full_debug_compact_and_growth_human_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            path = root / 'sample.py'
            path.write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            store(root, [review()])
            full = self.read_json(self.run_guard(root, 'sample.py', '--json'))
            debug = self.read_json(self.run_guard(root, 'sample.py', '--json', '--json-mode', 'debug'))
            compact = self.read_json(self.run_guard(root, 'sample.py', '--json', '--json-mode', 'compact'))
            self.assertEqual(full, debug)
            self.assertEqual(compact['guards']['complexity']['findings'], [])
            self.assertNotIn('REVIEW:', self.run_guard(root, 'sample.py').stdout)
            path.write_text(source('cyclomaticComplexity', 5), encoding='utf-8')
            human = self.run_guard(root, 'sample.py')
            self.assertIn('complexity 5', human.stdout)
            self.assertIn('accepted 4', human.stdout)
            compact = self.read_json(self.run_guard(root, 'sample.py', '--json', '--json-mode', 'compact'))
            self.assertEqual(compact['guards']['complexity']['findings'][0]['ratchetStatus'], 'grown')
            self.assertEqual(self.run_guard(root, 'sample.py', '--ci').returncode, 0)
