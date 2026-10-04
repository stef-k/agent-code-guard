"""Runner authority and actual working-tree policy in deterministic Git fixtures."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from agent_code_guard import code_guard, file_selection
from agent_code_guard.invocation import GitAuthority, load_configuration

from tests.helpers import CodeGuardTestCase, git, init_git, write_lines


CONFIG = '.agent-tools/code-guard.config.json'


def write_policy(root: Path, warn: int, relative: str = CONFIG, **document) -> Path:
    """Write the active artifact without changing invocation behavior in fixtures."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'guards': {'loc': {'warnAt': warn}}, **document}), encoding='utf-8')
    return path


def write_baselines(root: Path, allowance: int) -> list[str]:
    """Exercise all three persisted families with one deterministic allowance."""
    documents = {
        'loc': {'loc': {'files': [{'path': 'src/a.py', 'allowedLoc': allowance}]}},
        'markdown': {'markdownDocumentSize': {'files': [{'path': 'docs/a.md', 'allowedLines': allowance}]}},
        'callable-review': {'callableReviews': [{'path': 'src/a.py', 'embeddedLanguage': 'python',
            'callable': 'answer', 'guard': 'callableSize', 'allowedMeasured': allowance, 'reason': 'accepted'}]},
    }
    paths = []
    for name, document in documents.items():
        relative = f'.agent-tools/code-guard.{name}-baseline.json'
        path = root / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({'version': 1, **document}), encoding='utf-8')
        paths.append(relative)
    return paths


class PolicyGitTests(CodeGuardTestCase):
    def base(self, root: Path, warn: int = 400):
        """Create a committed policy/source base using the existing Git helper."""
        init_git(root)
        write_lines(root / 'src/a.py', 1)
        write_policy(root, warn)
        git(root, 'add', '.')
        git(root, 'commit', '-m', 'base')
        return git(root, 'rev-parse', 'HEAD').stdout.strip()

    def policy_reasons(self, result):
        data = self.read_json(result)
        self.assertEqual(result.returncode, 1, data)
        return data['guards']['policyRelaxation']['findings'][0]['reasons']

    def test_changed_and_staged_compare_head_to_working_tree_not_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / 'src/a.py', 1)
            write_policy(root, 350)
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'base')
            write_policy(root, 400)
            write_lines(root / 'src/a.py', 425)
            git(root, 'add', CONFIG, 'src/a.py')
            write_policy(root, 450)
            for mode in ('--changed-only', '--staged'):
                with self.subTest(mode=mode):
                    result = self.run_guard(root, 'src', mode, '--json')
                    data = self.read_json(result)
                    self.assertEqual((result.returncode, data['scope']['selected']), (1, 1))
                    reason = data['guards']['policyRelaxation']['findings'][0]['reasons'][0]
                    self.assertEqual((reason['before'], reason['after']), (350, 450))
                    self.assertEqual(data['requiredPolicies'], ['policyRelaxation'])
                    self.assertEqual((self.findings(result)[0]['warnAt'], self.findings(result)[0]['nativeStatus']), (450, 'ok'))

    def test_all_staged_baselines_compare_head_to_working_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root)
            paths = write_baselines(root, 900)
            git(root, 'add', '.agent-tools')
            git(root, 'commit', '-m', 'allowances')
            write_baselines(root, 901)
            git(root, 'add', '.agent-tools')
            write_baselines(root, 902)
            reasons = self.policy_reasons(self.run_guard(root, 'src', '--staged', '--json'))
            self.assertEqual({reason['artifact'] for reason in reasons}, set(paths))
            self.assertEqual([(reason['before'], reason['after']) for reason in reasons], [(900, 902)] * 3)

    def test_divergent_base_uses_merge_base_and_keeps_committed_source_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root, 350)
            git(root, 'branch', 'feature')
            write_policy(root, 500)
            write_lines(root / 'src/base-only.py', 1)
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'base advances')
            git(root, 'switch', 'feature')
            write_policy(root, 400)
            write_lines(root / 'src/feature.py', 1)
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'feature')
            write_policy(root, 450)
            write_lines(root / 'src/untracked.py', 1)
            result = self.run_guard(root, 'src', '--base-ref', 'main', '--json')
            reasons = self.policy_reasons(result)
            self.assertEqual([(reason['before'], reason['after']) for reason in reasons], [(350, 450)])
            self.assertEqual([finding['path'] for finding in self.findings(result)], ['src/feature.py'])

    def test_resolved_base_seam_is_reused_without_later_ref_queries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            base = self.base(root, 350)
            write_policy(root, 400)
            write_lines(root / 'src/feature.py', 1)
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'feature')
            head = git(root, 'rev-parse', 'HEAD').stdout.strip()
            write_policy(root, 450)
            args = code_guard.parser().parse_args(['src', '--base-ref', 'chosen-by-runner'])
            authority = GitAuthority(head, base)
            with patch.object(file_selection, 'resolve_git_authority', return_value=authority):
                context = file_selection.resolve_invocation(args, root, load_configuration(None, root))
            self.assertIs(context.git_authority, authority)
            self.assertEqual([item.reporting_path for item in context.selected_files], ['src/feature.py'])
            git(root, 'update-ref', 'refs/heads/main', base)
            original_run = file_selection.subprocess.run
            with patch('subprocess.run', wraps=original_run) as calls:
                data = code_guard.payload(code_guard.run_analysis(context, args))
            self.assertTrue(all(call.args[0][1] not in {'rev-parse', 'merge-base'} for call in calls.call_args_list))
            reason = data['guards']['policyRelaxation']['findings'][0]['reasons'][0]
            self.assertEqual((reason['before'], reason['after']), (350, 450))

    def test_unborn_modes_compare_untracked_policy_with_defaults(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / 'src/a.py', 1)
            write_policy(root, 500)
            write_baselines(root, 900)
            for mode in ('--changed-only', '--staged'):
                with self.subTest(mode=mode):
                    result = self.run_guard(root, 'src', mode, '--json')
                    reasons = self.policy_reasons(result)
                    self.assertEqual(len(reasons), 4)
                    threshold = next(reason for reason in reasons if reason['reasonCode'] == 'thresholdIncreased')
                    self.assertEqual((threshold['before'], threshold['after']), (400, 500))
            invalid = self.run_guard(root, '--base-ref', 'main', '--json')
            self.assertEqual(invalid.returncode, 3)
            self.assertIn('unable to compare base ref', self.read_json(invalid)['error'])

    def test_untracked_and_ignored_artifacts_outside_bounds_are_visible(self):
        for ignored in (False, True):
            with self.subTest(ignored=ignored), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                init_git(root)
                write_lines(root / 'src/a.py', 1)
                if ignored:
                    (root / '.gitignore').write_text('.agent-tools/\n', encoding='utf-8')
                git(root, 'add', '.')
                git(root, 'commit', '-m', 'source')
                write_policy(root, 500)
                write_baselines(root, 900)
                result = self.run_guard(root, 'src/a.py', '--staged', '--json')
                self.assertEqual(len(self.policy_reasons(result)), 4)
                self.assertEqual(self.read_json(result)['scope']['selected'], 0)

    def test_policy_remains_visible_when_all_sources_and_policy_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root)
            write_policy(root, 500, scope={'exclude': ['**']})
            write_baselines(root, 900)
            result = self.run_guard(root, '.', '--changed-only', '--scope-exclude', '.agent-tools/**', '--json')
            self.assertEqual(len(self.policy_reasons(result)), 5)
            self.assertEqual(self.read_json(result)['scope']['selected'], 0)

    def test_loc_exclusion_cannot_hide_policy_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root)
            path = write_policy(root, 500)
            document = json.loads(path.read_text(encoding='utf-8'))
            document['guards']['loc']['exclude'] = ['**']
            path.write_text(json.dumps(document), encoding='utf-8')
            reasons = self.policy_reasons(self.run_guard(root, 'src', '--staged', '--json'))
            self.assertEqual({reason['reasonCode'] for reason in reasons}, {'exclusionAdded', 'thresholdIncreased'})

    def test_deleting_config_restores_defaults_and_deleting_baselines_is_quiet(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root, 350)
            paths = write_baselines(root, 900)
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'allowances')
            (root / CONFIG).unlink()
            for relative in paths:
                (root / relative).unlink()
            reasons = self.policy_reasons(self.run_guard(root, 'src', '--changed-only', '--json'))
            self.assertEqual([(reason['reasonCode'], reason['before'], reason['after']) for reason in reasons],
                             [('thresholdIncreased', 350, 400)])
            write_policy(root, 350)
            result = self.run_guard(root, 'src', '--changed-only', '--json')
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.read_json(result)['guards']['policyRelaxation']['state'], 'pass')

    def test_subdirectory_uses_its_actual_auto_config_with_root_baselines(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root, 500)
            relative = 'src/' + CONFIG
            write_policy(root, 350, relative)
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'subdirectory config')
            write_policy(root, 450, relative)
            write_baselines(root, 900)
            reasons = self.policy_reasons(self.run_guard(root / 'src', '.', '--staged', '--json'))
            threshold = next(reason for reason in reasons if reason['reasonCode'] == 'thresholdIncreased')
            self.assertEqual((threshold['artifact'], threshold['before'], threshold['after']), (relative, 350, 450))
            self.assertEqual(len(reasons), 4)

    def test_owned_explicit_config_aliases_map_to_the_active_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root)
            path = write_policy(root, 350, 'policy/custom.json')
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'explicit config')
            write_policy(root, 450, 'policy/custom.json')
            for alias in ('policy/custom.json', 'policy/../policy/custom.json', str(path.resolve())):
                with self.subTest(alias=alias):
                    reason = self.policy_reasons(self.run_guard(root, 'src', '--staged', '--config', alias, '--json'))[0]
                    self.assertEqual((reason['artifact'], reason['before'], reason['after']), ('policy/custom.json', 350, 450))

    def test_external_config_errors_only_in_git_modes(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp)
            self.base(root)
            path = write_policy(Path(outside), 400)
            for mode in ('--changed-only', '--staged', '--base-ref'):
                arguments = (mode, 'HEAD') if mode == '--base-ref' else (mode,)
                result = self.run_guard(root, 'src', *arguments, '--config', str(path), '--json')
                self.assertEqual(result.returncode, 3)
                self.assertIn('outside the Git repository', self.read_json(result)['error'])
            self.assertEqual(self.run_guard(root, 'src', '--config', str(path), '--json').returncode, 0)

    def test_current_symlink_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root)
            alias = root / 'alias.json'
            try:
                alias.symlink_to(root / CONFIG)
            except OSError as exc:
                self.skipTest(f'symlinks unavailable: {exc}')
            result = self.run_guard(root, 'src', '--staged', '--config', str(alias), '--json')
            self.assertEqual(result.returncode, 3)
            self.assertIn('symlink', self.read_json(result)['error'])

    def test_config_symlink_ancestor_cannot_leave_and_reenter_repository(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp).resolve()
            self.base(root)
            link = root / 'link'
            try:
                link.symlink_to(Path(outside).resolve(), target_is_directory=True)
            except OSError as exc:
                self.skipTest(f'symlinks unavailable: {exc}')
            alias = link / '..' / root.name / CONFIG
            self.assertEqual(alias.resolve(), root / CONFIG)
            result = self.run_guard(root, 'src', '--staged', '--config', str(alias), '--json')
            self.assertEqual(result.returncode, 3)
            self.assertIn('symlink', self.read_json(result)['error'])

    def test_malformed_current_and_historical_config_fail_closed(self):
        for historical, text in ((False, '{'), (True, '{'),
                                 (False, '{"guards":{"loc":{"warnAt":true}}}'),
                                 (True, '{"guards":{"loc":{"warnAt":true}}}')):
            with self.subTest(historical=historical, text=text), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.base(root)
                (root / CONFIG).write_text(text, encoding='utf-8')
                if historical:
                    git(root, 'add', '.')
                    git(root, 'commit', '-m', 'invalid policy')
                    (root / CONFIG).unlink()
                result = self.run_guard(root, 'src', '--staged', '--json')
                self.assertEqual(result.returncode, 3)
                self.assertIn('guards.loc.warnAt' if 'warnAt' in text else 'Expecting property name', self.read_json(result)['error'])

    def test_malformed_or_unsupported_baselines_fail_even_after_deletion(self):
        for family in ('loc', 'markdown', 'callable-review'):
            for historical in (False, True):
                with self.subTest(family=family, historical=historical), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    self.base(root)
                    paths = write_baselines(root, 900)
                    path = root / f'.agent-tools/code-guard.{family}-baseline.json'
                    document = json.loads(path.read_text(encoding='utf-8'))
                    document['version'] = 2
                    path.write_text(json.dumps(document), encoding='utf-8')
                    if historical:
                        git(root, 'add', '.')
                        git(root, 'commit', '-m', 'invalid baseline')
                        for relative in paths:
                            (root / relative).unlink()
                    result = self.run_guard(root, 'src', '--staged', '--json')
                    self.assertEqual(result.returncode, 3)
                    self.assertIn('version must be the integer 1', self.read_json(result)['error'])

    def test_malformed_baseline_text_is_not_treated_as_missing(self):
        for family in ('loc', 'markdown', 'callable-review'):
            for historical in (False, True):
                with self.subTest(family=family, historical=historical), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    self.base(root)
                    path = root / f'.agent-tools/code-guard.{family}-baseline.json'
                    path.write_text('{', encoding='utf-8')
                    if historical:
                        git(root, 'add', '.')
                        git(root, 'commit', '-m', 'malformed baseline')
                        path.unlink()
                    result = self.run_guard(root, 'src', '--staged', '--json')
                    self.assertEqual(result.returncode, 3)
                    self.assertIn('invalid ', self.read_json(result)['error'])

    def test_historical_baselines_do_not_validate_targets_in_current_filesystem(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp)
            self.base(root)
            baseline = root / '.agent-tools' / 'code-guard.loc-baseline.json'
            baseline.write_text(json.dumps({'version': 1, 'loc': {'files': [
                {'path': 'retired/a.py', 'allowedLoc': 900},
            ]}}), encoding='utf-8')
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'historical allowance')
            baseline.unlink()
            try:
                (root / 'retired').symlink_to(Path(outside), target_is_directory=True)
            except OSError as exc:
                self.skipTest(f'symlinks unavailable: {exc}')
            result = self.run_guard(root, 'src', '--staged', '--json')
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.read_json(result)['guards']['policyRelaxation']['state'], 'pass')

    def test_current_baseline_parent_cannot_hide_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root)
            explicit = write_policy(root, 400, 'custom.json')
            (root / CONFIG).unlink()
            (root / '.agent-tools').rmdir()
            (root / '.agent-tools').write_text('not a directory', encoding='utf-8')
            result = self.run_guard(root, 'src', '--staged', '--config', str(explicit), '--json')
            self.assertEqual(result.returncode, 3)
            self.assertIn('baseline directory must be a real directory', self.read_json(result)['error'])
            plain = self.run_guard(root, 'src', '--config', str(explicit), '--json')
            self.assertEqual(plain.returncode, 0, plain.stdout)
            self.assertNotIn('policyRelaxation', self.read_json(plain)['guards'])

    def test_unsafe_historical_blob_tree_and_gitlink_shapes_fail_closed(self):
        for mode, relative in (('120000', CONFIG), ('120000', '.agent-tools'),
                               ('100644', '.agent-tools'), ('160000', '.agent-tools')):
            with self.subTest(mode=mode, relative=relative), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                base = self.base(root)
                # Only the index is made unsafe; the actual working-tree config stays valid.
                if relative == '.agent-tools':
                    git(root, 'rm', '--cached', CONFIG)
                object_id = base if mode == '160000' else git(root, 'hash-object', '-w', CONFIG).stdout.strip()
                git(root, 'update-index', '--add', '--cacheinfo', mode, object_id, relative)
                git(root, 'commit', '-m', 'unsafe historical artifact')
                result = self.run_guard(root, 'src', '--staged', '--json')
                self.assertEqual(result.returncode, 3)
                self.assertIn('unsafe historical policy', self.read_json(result)['error'])

    def test_invalid_base_and_broken_head_are_authority_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base(root)
            result = self.run_guard(root, 'src', '--base-ref', 'missing', '--json')
            self.assertEqual(result.returncode, 3)
            self.assertIn('unable to compare base ref', self.read_json(result)['error'])
            (root / '.git' / 'HEAD').write_text('f' * 40 + '\n', encoding='ascii')
            for mode in ('--changed-only', '--staged'):
                result = self.run_guard(root, 'src', mode, '--json')
                self.assertEqual(result.returncode, 3)
                self.assertIn('unable to resolve HEAD', self.read_json(result)['error'])

    def test_plain_analysis_omits_policy_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / 'a.py', 1)
            write_policy(root, 500)
            for arguments in (('.',), ('a.py',)):
                result = self.run_guard(root, *arguments, '--json')
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('policyRelaxation', self.read_json(result)['guards'])
