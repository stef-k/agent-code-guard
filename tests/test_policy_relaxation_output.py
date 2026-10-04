"""Policy result routing, bounded output, and independent failure dominance."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase, REPO_ROOT, git, init_git, write_lines


class PolicyOutputTests(CodeGuardTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        init_git(self.root)
        write_lines(self.root / 'a.py', 1)
        self.config_path = self.root / '.agent-tools' / 'code-guard.config.json'
        self.config_path.parent.mkdir()
        self.write_config({'guards': {'loc': {'warnAt': 400}}})
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'base')

    def write_config(self, document):
        self.config_path.write_text(json.dumps(document), encoding='utf-8')

    def test_pass_routing_and_json_modes(self):
        for options in (('--json',), ('--json', '--json-mode', 'compact'), ('--json', '--json-mode', 'debug')):
            with self.subTest(options=options):
                result = self.run_guard(self.root, '.', '--changed-only', *options)
                data = self.read_json(result)
                self.assertEqual((result.returncode, data['overall'], data['requiredPolicies']), (0, 'pass', []))
                self.assertEqual(data['guards']['policyRelaxation'], {'state': 'pass', 'findings': []})

    def test_review_keeps_same_details_in_all_json_modes_and_ci(self):
        self.write_config({'guards': {'loc': {'warnAt': 500}}})
        expected = None
        for ci in (False, True):
            ci_args = ('--ci',) if ci else ()
            for options in (('--json',), ('--json', '--json-mode', 'compact'), ('--json', '--json-mode', 'debug')):
                with self.subTest(ci=ci, options=options):
                    result = self.run_guard(self.root, 'a.py', '--staged', *ci_args, *options)
                    data = self.read_json(result)
                    self.assertEqual((result.returncode, data['overall']), (0 if ci else 1, 'review'))
                    self.assertEqual(data['requiredPolicies'], ['policyRelaxation'])
                    aggregate = data['guards']['policyRelaxation']
                    expected = aggregate if expected is None else expected
                    self.assertEqual(aggregate, expected)
            human = self.run_guard(self.root, 'a.py', '--staged', *ci_args)
            self.assertEqual(human.returncode, 0 if ci else 1)
            self.assertIn('REVIEW: policyRelaxation', human.stdout)
            self.assertIn('400 -> 500', human.stdout)
            self.assertIn('Required policies: policyRelaxation', human.stdout)

    def test_large_serialized_and_human_aggregate_is_capped_and_deterministic(self):
        baseline = self.config_path.parent / 'code-guard.loc-baseline.json'
        baseline.write_text(json.dumps({'version': 1, 'loc': {'files': [
            {'path': f'src/{index:03}.py', 'allowedLoc': 900} for index in range(35)
        ]}}), encoding='utf-8')
        self.write_config({'scope': {'exclude': ['src/**', 'src/generated/**']}})
        first = self.run_guard(self.root, 'a.py', '--staged', '--json')
        self.assertEqual(first.returncode, 1, first.stdout)
        data = self.read_json(first)
        finding = data['guards']['policyRelaxation']['findings'][0]
        self.assertEqual((finding['totalReasons'], len(finding['reasons']), finding['omittedReasons']), (37, 20, 17))
        self.assertNotIn('src/034.py', first.stdout)
        second = self.run_guard(self.root, 'a.py', '--staged', '--json')
        self.assertEqual(first.stdout, second.stdout)
        human = self.run_guard(self.root, 'a.py', '--staged')
        self.assertIn('37 policy reasons', human.stdout)
        self.assertIn('Omitted reason details: 17', human.stdout)
        self.assertEqual(human.stdout.count(']: '), 20)

    def test_conservative_wording_describes_declarations_and_topology(self):
        self.write_config({'scope': {'exclude': ['src/**', 'src/generated/**']}, 'guards': {'loc': {
            'overrides': [{'match': ['*.py'], 'warnAt': 350, 'failAt': 550}],
        }}})
        human = self.run_guard(self.root, 'a.py', '--staged')
        self.assertIn('Exclusion declaration added', human.stdout)
        self.assertIn('topology changed', human.stdout)
        self.assertIn('path-specific weakening is not proven', human.stdout)
        self.assertIn('"entries": 0', human.stdout)
        self.assertIn('"entries": 1', human.stdout)

    def test_loc_fail_and_syntax_incomplete_dominate_but_retain_policy_review(self):
        self.write_config({'guards': {'loc': {'warnAt': 500}}})
        for broken in (False, True):
            write_lines(self.root / 'a.py', 601)
            if broken:
                with (self.root / 'a.py').open('a', encoding='utf-8') as handle:
                    handle.write('def broken(:\n')
            for ci in (False, True):
                with self.subTest(broken=broken, ci=ci):
                    ci_args = ('--ci',) if ci else ()
                    result = self.run_guard(self.root, '.', '--changed-only', '--json', '--json-mode', 'compact', *ci_args)
                    data = self.read_json(result)
                    self.assertEqual((result.returncode, data['overall']), (3, 'incomplete') if broken else (2, 'fail'))
                    self.assertEqual(data['guards']['policyRelaxation']['state'], 'review')
                    self.assertEqual(data['requiredPolicies'], ['loc', 'policyRelaxation'])
                    if broken:
                        self.assertEqual(data['completedOverall'], 'fail')
                        self.assertTrue(data['guards']['policyRelaxation']['complete'])

    def test_git_comparison_preserves_no_source_parser_execution(self):
        self.write_config({'guards': {name: {'enabled': False} for name in (
            'callableSize', 'nesting', 'cyclomaticComplexity', 'markdownDocumentSize', 'markdownSectionSize',
        )}})
        script = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from agent_code_guard.code_guard import main
sys.argv = ['code-guard', 'a.py', '--staged', '--ci', '--json']
status = main()
loaded = [name for name in sys.modules if name.startswith(('agent_code_guard.analysis', 'tree_sitter'))]
print(json.dumps({'status': status, 'loaded': loaded}))
"""
        result = subprocess.run([sys.executable, '-S', '-c', script, str(REPO_ROOT / 'src')],
                                cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]), {'status': 0, 'loaded': []})
        self.assertEqual(json.loads(result.stdout.rsplit('\n{', 1)[0])['guards']['policyRelaxation']['state'], 'review')
