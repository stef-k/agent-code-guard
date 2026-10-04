"""Explicit acceptance/maintenance and existing scope, safety, and evidence boundaries."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from agent_code_guard import code_guard
from agent_code_guard.analysis import pipeline
from agent_code_guard.analysis.errors import ProviderUnavailableError
from agent_code_guard.file_selection import resolve_invocation
from agent_code_guard.invocation import AnalysisContext, SelectedFile, load_configuration
from tests.helpers import CodeGuardTestCase, git, init_git
from tests.test_callable_review_baseline import BASELINE, GUARDS, REASON, configure, review, source, store


def accept_options(guard='cyclomaticComplexity', identity='sample.selected', language='python'):
    """Explicit selector and rationale used by public lifecycle invocations."""
    return '--accept-callable-review', guard, language, identity, '--reason', REASON


def entries(root):
    return json.loads((root / BASELINE).read_text(encoding='utf-8'))['callableReviews']


class CallableReviewLifecycleTests(CodeGuardTestCase):
    def test_acceptance_records_only_one_exact_review_for_each_guard(self):
        for guard, result_id in GUARDS.items():
            with self.subTest(guard=guard), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                configure(root, guard)
                path = root / 'sample.py'
                path.write_text(source(guard, 4) + source(guard, 4, 'other'), encoding='utf-8')
                result = self.run_guard(root, 'sample.py', *accept_options(guard))
                self.assertEqual((result.returncode, result.stderr), (0, ''))
                self.assertEqual(entries(root), [review(guard)])
                data = self.read_json(self.run_guard(root, 'sample.py', '--json'))
                self.assertEqual([item['state'] for item in data['guards'][result_id]['findings']], ['pass', 'review'])
                baseline = root / BASELINE
                before = baseline.read_bytes()
                repeat = self.run_guard(root, 'sample.py', *accept_options(guard))
                self.assertEqual(repeat.returncode, 3)
                self.assertEqual(baseline.read_bytes(), before)
                path.write_text(source(guard, 5), encoding='utf-8')
                growth = self.run_guard(root, 'sample.py', *accept_options(guard))
                self.assertEqual(growth.returncode, 3)
                self.assertIn('cannot replace or increase', growth.stderr)
                self.assertEqual(baseline.read_bytes(), before)

    def test_acceptance_requires_review_unique_identity_and_nonempty_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            path = root / 'sample.py'
            path.write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            for options in (
                ('--accept-callable-review', 'cyclomaticComplexity', 'python', 'sample.selected'),
                (*accept_options()[:-1], ' '), accept_options('complexity'),
                accept_options(identity='missing'), accept_options(language='javascript'),
            ):
                with self.subTest(options=options):
                    result = self.run_guard(root, 'sample.py', *options)
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertFalse((root / BASELINE).exists())
            path.write_text(source('cyclomaticComplexity', 2), encoding='utf-8')
            self.assertEqual(self.run_guard(root, 'sample.py', *accept_options()).returncode, 3)
            path.write_text(source('cyclomaticComplexity', 4) * 2, encoding='utf-8')
            ambiguous = self.run_guard(root, 'sample.py', *accept_options())
            self.assertEqual(ambiguous.returncode, 3)
            self.assertIn('ambiguous callable review', ambiguous.stderr)
            self.assertFalse((root / BASELINE).exists())

    def test_maintenance_is_bounded_non_increasing_and_prunes_only_explicitly(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            configure(root)
            (root / 'sub').mkdir()
            path = root / 'sub/sample.py'
            path.write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            baseline = store(root, [review(path='sub/sample.py'), review(path='outside.py', callable='outside.selected')])
            path.write_text(source('cyclomaticComplexity', 5), encoding='utf-8')
            before = baseline.read_bytes()
            result = self.run_guard(root, 'sub', '--update-callable-review-baseline')
            self.assertEqual(result.returncode, 3)
            self.assertEqual(baseline.read_bytes(), before)
            path.write_text(source('cyclomaticComplexity', 3), encoding='utf-8')
            (root / 'sub/new.py').write_text(source('cyclomaticComplexity', 5), encoding='utf-8')
            result = self.run_guard(root, 'sub', '--update-callable-review-baseline')
            self.assertIn('1 lowered', result.stdout)
            self.assertEqual(entries(root)[1]['allowedMeasured'], 3)
            self.assertEqual(len(entries(root)), 2)
            stamp = baseline.stat().st_mtime_ns
            self.assertEqual(self.run_guard(root, 'sub', '--update-callable-review-baseline').returncode, 0)
            self.assertEqual(baseline.stat().st_mtime_ns, stamp)
            path.write_text(source('cyclomaticComplexity', 2), encoding='utf-8')
            self.assertEqual(self.run_guard(root, 'sub', '--update-callable-review-baseline').returncode, 0)
            self.assertEqual(entries(root), [review(path='outside.py', callable='outside.selected')])
            before = baseline.read_bytes()
            stale = self.run_guard(root, '.', '--update-callable-review-baseline')
            self.assertIn('1 stale', stale.stdout)
            self.assertIn('--prune-stale-callable-reviews', stale.stdout)
            self.assertEqual(baseline.read_bytes(), before)
            pruned = self.run_guard(root, '.', '--update-callable-review-baseline', '--prune-stale-callable-reviews')
            self.assertEqual(pruned.returncode, 0, pruned.stderr)
            self.assertEqual(entries(root), [])

    def test_write_modes_reject_analysis_modes_and_require_explicit_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            (root / 'sample.py').write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            for mode in (accept_options(), ('--update-callable-review-baseline',)):
                for options in (
                    ('--json',), ('--json-mode', 'debug'), ('--ci',), ('--changed-only',), ('--staged',),
                    ('--base-ref', 'HEAD'), ('--version',), ('--skill-path',), ('--export-skill', 'target'),
                    ('--create-loc-baseline',), ('--update-loc-baseline',),
                    ('--create-markdown-baseline',), ('--update-markdown-baseline',),
                    ('--warn', '500'), ('--count-blank-lines',), ('--exclude', '*.py'),
                ):
                    with self.subTest(mode=mode, options=options):
                        result = self.run_guard(root, 'sample.py', *mode, *options)
                        self.assertEqual((result.returncode, result.stdout), (3, ''))
                        self.assertFalse((root / BASELINE).exists())
                self.assertEqual(self.run_guard(root, *mode).returncode, 3)
            self.assertEqual(self.run_guard(root, '.', *accept_options()).returncode, 3)
            self.assertEqual(self.run_guard(root, 'sample.py', '--reason', REASON).returncode, 3)
            self.assertEqual(self.run_guard(root, 'sample.py', '--prune-stale-callable-reviews').returncode, 3)
            excluded = self.run_guard(root, 'sample.py', *accept_options(), '--scope-exclude', '*.py')
            self.assertEqual(excluded.returncode, 3)

    def test_scope_exclusion_disabled_guard_and_threshold_changes_preserve_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            (root / 'sample.py').write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            baseline = store(root, [review()])
            before = baseline.read_bytes()
            excluded = self.run_guard(root, '.', '--scope-exclude', '*.py', '--update-callable-review-baseline',
                                      '--prune-stale-callable-reviews')
            self.assertEqual(excluded.returncode, 0, excluded.stderr)
            self.assertEqual(baseline.read_bytes(), before)
            configure(root, threshold=5)
            data = self.read_json(self.run_guard(root, 'sample.py', '--json'))
            self.assertEqual(data['guards']['complexity']['findings'][0]['ratchetStatus'], 'notNeeded')
            self.assertEqual(baseline.read_bytes(), before)
            config = root / '.agent-tools/code-guard.config.json'
            document = json.loads(config.read_text(encoding='utf-8'))
            document['guards']['cyclomaticComplexity'] = {'enabled': False}
            config.write_text(json.dumps(document), encoding='utf-8')
            with patch.object(pipeline, 'analyze_files_for_runner', side_effect=AssertionError('disabled guard activated')):
                args = code_guard.parser().parse_args(['sample.py', '--config', str(config)])
                context = resolve_invocation(args, root, load_configuration(str(config), root))
                data = code_guard.payload(code_guard.run_analysis(context, args))
            self.assertNotIn('complexity', data['guards'])
            self.assertEqual(baseline.read_bytes(), before)

    def test_explicit_file_symlinks_and_outside_scope_cannot_gain_allowances(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as other:
            root, outside = Path(temp), Path(other)
            configure(root)
            (root / 'sample.py').write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            (outside / 'external.py').write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            try:
                (root / 'alias.py').symlink_to(root / 'sample.py')
            except OSError as exc:
                self.skipTest(f'file symlinks unavailable: {exc}')
            self.assertEqual(self.run_guard(root, 'alias.py', *accept_options()).returncode, 3)
            self.assertEqual(self.run_guard(root, str(outside / 'external.py'), *accept_options()).returncode, 3)
            self.assertEqual(self.run_guard(root, 'sample.py', *accept_options()).returncode, 0)
            self.assertEqual(self.run_guard(root, 'alias.py', '--json').returncode, 1)
            self.assertEqual(self.run_guard(root, 'sample.py', 'alias.py', '--json').returncode, 0)
            self.assertEqual(self.run_guard(root, str(outside), '--json').returncode, 3)
            baseline = root / BASELINE
            before = baseline.read_bytes()
            (root / 'sample.py').unlink()
            (root / 'sample.py').symlink_to(outside / 'external.py')
            for options in (('--json',), ('--update-callable-review-baseline', '--prune-stale-callable-reviews')):
                self.assertEqual(self.run_guard(root, '.', *options).returncode, 3)
                self.assertEqual(baseline.read_bytes(), before)

    def test_incomplete_evidence_is_preserved_and_blocks_all_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            (root / 'sample.py').write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            (root / 'broken.py').write_text('def broken(:\n', encoding='utf-8')
            baseline = store(root, [review()])
            before = baseline.read_bytes()
            result = self.run_guard(root, '.', '--json', '--json-mode', 'compact', '--ci')
            data = self.read_json(result)
            self.assertEqual((result.returncode, data['overall'], data['completedOverall']), (3, 'incomplete', 'pass'))
            self.assertEqual(data['guards']['complexity']['complete'], False)
            self.assertEqual(data['guards']['complexity']['unavailablePaths'], ['broken.py'])
            self.assertEqual(data['guards']['complexity']['findings'], [])
            result = self.run_guard(root, '.', '--update-callable-review-baseline', '--prune-stale-callable-reviews')
            self.assertEqual(result.returncode, 3)
            self.assertIn('complete analysis', result.stderr)
            (root / 'sample.py').write_text('def selected(:\n', encoding='utf-8')
            result = self.run_guard(root, 'sample.py', *accept_options())
            self.assertEqual(result.returncode, 3)
            self.assertIn('complete analysis', result.stderr)
            self.assertEqual(baseline.read_bytes(), before)

    def test_provider_failure_and_single_runner_pass_remain_authoritative(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            (root / 'sample.py').write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            store(root, [review()])
            config = root / '.agent-tools/code-guard.config.json'
            args = code_guard.parser().parse_args(['sample.py', '--config', str(config)])
            context = resolve_invocation(args, root, load_configuration(str(config), root))
            with patch.object(pipeline, 'analyze_files_for_runner', wraps=pipeline.analyze_files_for_runner) as analyze:
                result = code_guard.run_analysis(context, args)
            analyze.assert_called_once()
            self.assertEqual(code_guard.payload(result)['overall'], 'pass')
            with patch.object(pipeline.TreeSitterProvider, 'parse',
                              side_effect=ProviderUnavailableError('grammar unavailable', language='python')):
                data = code_guard.payload(code_guard.run_analysis(context, args))
            self.assertEqual(data['overall'], 'incomplete')
            self.assertEqual(data['unavailable'][0]['kind'], 'provider')
            self.assertNotIn('callableReviewBaseline', data)

    def test_storage_links_and_changed_physical_scope_fail_before_analysis(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as other:
            root, outside = Path(temp), Path(other)
            configure(root)
            path = root / 'sample.py'
            path.write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            baseline = store(root, [review()])
            external = outside / 'sample.py'
            external.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
            linked_baseline = outside / 'baseline.json'
            linked_baseline.write_bytes(baseline.read_bytes())
            try:
                (root / 'link').symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f'directory symlinks unavailable: {exc}')
            store(root, [review(path='link/sample.py')])
            self.assertEqual(self.run_guard(root, 'sample.py', '--json').returncode, 3)
            baseline.unlink()
            baseline.symlink_to(linked_baseline)
            self.assertEqual(self.run_guard(root, 'sample.py', '--json').returncode, 3)
            self.assertEqual(self.run_guard(root, 'sample.py', *accept_options()).returncode, 3)
            baseline.unlink()
            store(root, [])
            config = root / '.agent-tools/code-guard.config.json'
            args = code_guard.parser().parse_args(['sample.py', '--config', str(config)])
            context = resolve_invocation(args, root, load_configuration(str(config), root))
            path.unlink()
            path.symlink_to(external)
            with patch.object(pipeline, 'analyze_files_for_runner', side_effect=AssertionError('outside source parsed')):
                with self.assertRaisesRegex(ValueError, 'baseline analysis scope is outside analysis root'):
                    code_guard.run_analysis(context, args)
            (root / '.agent-tools').rename(outside / 'data')
            (root / '.agent-tools').symlink_to(outside / 'data', target_is_directory=True)
            self.assertEqual(self.run_guard(root, '.', '--json').returncode, 3)

    def test_growth_aborts_a_multi_entry_maintenance_proposal_without_partial_lowering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            (root / 'a.py').write_text(source('cyclomaticComplexity', 3), encoding='utf-8')
            (root / 'b.py').write_text(source('cyclomaticComplexity', 5), encoding='utf-8')
            baseline = store(root, [review(path=f'{name}.py', callable=f'{name}.selected') for name in ('a', 'b')])
            before = baseline.read_bytes()
            result = self.run_guard(root, '.', '--update-callable-review-baseline')
            self.assertEqual(result.returncode, 3)
            self.assertEqual(baseline.read_bytes(), before)

    def test_two_complexity_seventeen_reviews_keep_default_threshold_and_unaccepted_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'offenders_patterns.py'
            path.write_text(source('cyclomaticComplexity', 17, '_auth')
                            + source('cyclomaticComplexity', 17, '_analyze_pair'), encoding='utf-8')
            for name in ('_auth', '_analyze_pair'):
                result = self.run_guard(root, 'offenders_patterns.py',
                                        *accept_options(identity=f'offenders_patterns.{name}'))
                self.assertEqual(result.returncode, 0, result.stderr)
            accepted = self.read_json(self.run_guard(root, 'offenders_patterns.py', '--json'))
            self.assertEqual(accepted['guards']['complexity']['state'], 'pass')
            self.assertEqual([item['allowedMeasured'] for item in accepted['guards']['complexity']['findings']], [17, 17])
            self.assertEqual([item['thresholds'] for item in accepted['guards']['complexity']['findings']],
                             [{'reviewAt': 15}, {'reviewAt': 15}])
            path.write_text(path.read_text(encoding='utf-8') + source('cyclomaticComplexity', 16, 'new'), encoding='utf-8')
            data = self.read_json(self.run_guard(root, 'offenders_patterns.py', '--json'))
            self.assertEqual(data['guards']['complexity']['findings'][-1]['state'], 'review')

    def test_renamed_stale_entry_and_disabled_entry_are_not_auto_pruned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            (root / 'sample.py').write_text(source('cyclomaticComplexity', 4, 'renamed'), encoding='utf-8')
            baseline = store(root, [review(), review('nesting', 3)])
            before = baseline.read_bytes()
            self.assertIn('STALE callable review', self.run_guard(root, 'sample.py').stdout)
            self.assertEqual(baseline.read_bytes(), before)
            result = self.run_guard(root, 'sample.py', '--update-callable-review-baseline')
            self.assertIn('1 stale', result.stdout)
            self.assertEqual(len(entries(root)), 2)
            result = self.run_guard(root, 'sample.py', '--update-callable-review-baseline', '--prune-stale-callable-reviews')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(entries(root), [review('nesting', 3)])

    def test_git_selectors_read_allowances_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            configure(root)
            path = root / 'sample.py'
            path.write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            store(root, [review()])
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'accepted review')
            path.write_text('# unrelated line\n' + path.read_text(encoding='utf-8'), encoding='utf-8')
            self.assertEqual(self.run_guard(root, '.', '--changed-only', '--json').returncode, 0)
            git(root, 'add', 'sample.py')
            self.assertEqual(self.run_guard(root, '.', '--staged', '--json').returncode, 0)
            git(root, 'commit', '-m', 'move coordinates')
            self.assertEqual(self.run_guard(root, '.', '--base-ref', 'HEAD~1', '--json').returncode, 0)

    def test_all_guards_remain_disabled_even_with_an_ambiguous_allowance(self):
        for guard, result_id in GUARDS.items():
            with self.subTest(guard=guard), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                configure(root, guard)
                (root / 'sample.py').write_text(source(guard, 4) * 2, encoding='utf-8')
                baseline = store(root, [review(guard)])
                config = root / '.agent-tools/code-guard.config.json'
                document = json.loads(config.read_text(encoding='utf-8'))
                document['guards'][guard] = {'enabled': False}
                config.write_text(json.dumps(document), encoding='utf-8')
                before = baseline.read_bytes()
                result = self.run_guard(root, 'sample.py', '--json')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(result_id, self.read_json(result)['guards'])
                self.assertEqual(baseline.read_bytes(), before)

    def test_persisted_path_is_physical_even_when_reporting_path_differs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configure(root)
            path = root / 'sample.py'
            path.write_text(source('cyclomaticComplexity', 4), encoding='utf-8')
            store(root, [review()])
            config = root / '.agent-tools/code-guard.config.json'
            document = load_configuration(str(config), root)
            context = AnalysisContext(root, document, (SelectedFile('display.py', path),))
            args = code_guard.parser().parse_args(['sample.py', '--config', str(config)])
            data = code_guard.payload(code_guard.run_analysis(context, args))
            finding = data['guards']['complexity']['findings'][0]
            self.assertEqual((finding['path'], finding['state'], finding['allowedMeasured']), ('display.py', 'pass', 4))
