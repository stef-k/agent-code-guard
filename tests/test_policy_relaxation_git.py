"""Runner authority and actual working-tree policy in deterministic Git fixtures."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase, git, init_git, write_lines


CONFIG = '.agent-tools/code-guard.config.json'


def write_policy(root: Path, warn: int, relative: str = CONFIG, **document) -> Path:
    """Write the active artifact without changing invocation behavior in fixtures."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'guards': {'loc': {'warnAt': warn}}, **document}), encoding='utf-8')
    return path


class PolicyGitTests(CodeGuardTestCase):
    def test_changed_and_staged_compare_head_to_working_tree_not_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / 'src/a.py', 1)
            write_policy(root, 350)
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'base')
            write_policy(root, 400)
            git(root, 'add', CONFIG)
            write_policy(root, 450)
            for mode in ('--changed-only', '--staged'):
                with self.subTest(mode=mode):
                    result = self.run_guard(root, 'src', mode, '--json')
                    data = self.read_json(result)
                    self.assertEqual((result.returncode, data['scope']['selected']), (1, 0))
                    reason = data['guards']['policyRelaxation']['findings'][0]['reasons'][0]
                    self.assertEqual((reason['before'], reason['after']), (350, 450))
                    self.assertEqual(data['requiredPolicies'], ['policyRelaxation'])

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

