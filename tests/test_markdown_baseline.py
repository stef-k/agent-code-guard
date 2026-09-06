from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase, git, init_git, write_lines


BASELINE = Path('.agent-tools/code-guard.markdown-baseline.json')


def entries(root: Path) -> list[dict]:
    return json.loads((root / BASELINE).read_text(encoding='utf-8'))['markdownDocumentSize']['files']


class MarkdownBaselineTests(CodeGuardTestCase):
    def test_document_lifecycle_outputs_and_independent_section_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            document = root / 'architecture.md'
            write_lines(document, 845)
            write_lines(root / 'boundary.md', 800)
            ordinary = self.run_guard(root, '.', '--json')
            self.assertEqual(ordinary.returncode, 1)
            self.assertFalse((root / BASELINE).exists())
            self.assertNotIn('baselineLines', self.read_json(ordinary)['guards']['markdownDocumentSize']['findings'][0])
            created = self.run_guard(root, '.', '--create-markdown-baseline')
            self.assertEqual((created.returncode, created.stderr), (0, ''))
            self.assertEqual(entries(root), [{'path': 'architecture.md', 'allowedLines': 845}])
            before = (root / BASELINE).read_bytes()
            accepted = self.run_guard(root, '.', '--json')
            self.assertEqual(accepted.returncode, 0)
            finding = self.read_json(accepted)['guards']['markdownDocumentSize']['findings'][0]
            self.assertEqual((finding['state'], finding['baselineLines'], finding['ratchetStatus']), ('pass', 845, 'within'))
            self.assertEqual(finding['thresholds'], {'reviewAt': 800})
            self.assertEqual(self.read_json(accepted)['requiredPolicies'], [])
            self.assertIn('baseline 845, within', self.run_guard(root, '.').stdout)
            compact = self.run_guard(root, '.', '--json', '--json-mode', 'compact')
            self.assertEqual(self.read_json(compact)['guards']['markdownDocumentSize']['findings'], [])
            write_lines(document, 840)
            self.assertEqual(self.run_guard(root, '.', '--json').returncode, 0)
            self.assertEqual((root / BASELINE).read_bytes(), before)
            lowered = self.run_guard(root, '.', '--update-markdown-baseline')
            self.assertIn('1 lowered', lowered.stdout)
            self.assertEqual(entries(root)[0]['allowedLines'], 840)
            before = (root / BASELINE).read_bytes()
            write_lines(document, 846)
            growth = self.run_guard(root, '.', '--json')
            finding = self.read_json(growth)['guards']['markdownDocumentSize']['findings'][0]
            self.assertEqual((growth.returncode, finding['state'], finding['ratchetStatus']), (1, 'review', 'exceeded'))
            self.assertEqual(self.run_guard(root, '.', '--ci').returncode, 0)
            self.assertEqual(self.run_guard(root, '.', '--update-markdown-baseline').returncode, 3)
            self.assertEqual((root / BASELINE).read_bytes(), before)
            write_lines(document, 800)
            write_lines(root / 'new.md', 845)
            normal = self.read_json(self.run_guard(root, '.', '--json'))
            by_path = {item['path']: item for item in normal['guards']['markdownDocumentSize']['findings']}
            self.assertEqual(by_path['architecture.md']['ratchetStatus'], 'notNeeded')
            self.assertEqual(by_path['new.md']['state'], 'review')
            self.assertEqual(self.run_guard(root, '.', '--update-markdown-baseline').returncode, 0)
            self.assertEqual(entries(root), [])
            document.write_text('# Section\n' + 'body\n' * 799, encoding='utf-8')
            self.assertEqual(self.read_json(self.run_guard(root, 'architecture.md', '--json'))['guards']['markdownSectionSize']['state'], 'review')

    def test_bounded_update_prunes_deletions_exclusions_and_never_adds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            for name in ('docs/lower.md', 'docs/deleted.md', 'other.md'):
                write_lines(root / name, 805)
            self.assertEqual(self.run_guard(root, '.', '--create-markdown-baseline').returncode, 0)
            before = (root / BASELINE).read_bytes()
            self.assertEqual(self.run_guard(root, '.', '--create-markdown-baseline').returncode, 3)
            self.assertEqual((root / BASELINE).read_bytes(), before)
            write_lines(root / 'docs/lower.md', 802)
            (root / 'docs/deleted.md').unlink()
            write_lines(root / 'docs/new.md', 805)
            result = self.run_guard(root / 'docs', '.', '--update-markdown-baseline')
            self.assertEqual((result.returncode, result.stderr), (0, ''))
            self.assertEqual(entries(root), [
                {'path': 'docs/lower.md', 'allowedLines': 802},
                {'path': 'other.md', 'allowedLines': 805},
            ])
            stamp = (root / BASELINE).stat().st_mtime_ns
            self.assertEqual(self.run_guard(root, '.', '--update-markdown-baseline').returncode, 0)
            self.assertEqual((root / BASELINE).stat().st_mtime_ns, stamp)
            self.assertEqual(self.run_guard(root, 'docs', '--scope-exclude', 'docs/**', '--update-markdown-baseline').returncode, 0)
            self.assertEqual(entries(root), [{'path': 'other.md', 'allowedLines': 805}])

    def test_configuration_and_git_selection_preserve_document_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            (root / '.agent-tools').mkdir()
            config = root / '.agent-tools/code-guard.config.json'
            config.write_text(json.dumps({'version': 1, 'guards': {
                'loc': {'enabled': False}, 'markdownDocumentSize': {'reviewAt': 3},
            }, 'scope': {'exclude': ['excluded.md']}}), encoding='utf-8')
            write_lines(root / 'accepted.MD', 5)
            write_lines(root / 'excluded.md', 5)
            self.assertEqual(self.run_guard(root, '.', '--create-markdown-baseline').returncode, 0)
            self.assertEqual(entries(root), [{'path': 'accepted.MD', 'allowedLines': 5}])
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'accepted documents')
            write_lines(root / 'accepted.MD', 6)
            result = self.run_guard(root, '.', '--changed-only', '--json')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(self.read_json(result)['guards']['markdownDocumentSize']['findings'][0]['ratchetStatus'], 'exceeded')
            config.write_text(json.dumps({'version': 1, 'guards': {'markdownDocumentSize': {'enabled': False}}}), encoding='utf-8')
            self.assertEqual(self.run_guard(root, '.', '--update-markdown-baseline').returncode, 3)

    def test_malformed_baselines_fail_closed_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / 'doc.md', 845)
            baseline = root / BASELINE
            baseline.parent.mkdir()
            valid_entry = {'path': 'doc.md', 'allowedLines': 845}
            invalid_files = [[valid_entry, valid_entry]]
            invalid_files.extend(
                [{'path': path, 'allowedLines': 845}]
                for path in ('../doc.md', '/doc.md', 'C:/doc.md', './doc.md', 'a//doc.md', 'a\\doc.md', 'doc.py')
            )
            invalid_files.extend(
                [{'path': 'doc.md', 'allowedLines': value}]
                for value in (True, 0, -1, 845.0, '845')
            )
            documents = [json.dumps({'version': 1, 'markdownDocumentSize': {'files': files}}) for files in invalid_files]
            documents.extend((
                '{',
                '{"version":1,"version":1,"markdownDocumentSize":{"files":[]}}',
                '{"version":1.0,"markdownDocumentSize":{"files":[]}}',
                '{"version":1,"markdownDocumentSize":{"files":[]},"unknown":true}',
            ))
            for content in documents:
                with self.subTest(content=content):
                    baseline.write_text(content, encoding='utf-8')
                    for mode in ('--json', '--update-markdown-baseline'):
                        self.assertEqual(self.run_guard(root, '.', mode).returncode, 3)
                        self.assertEqual(baseline.read_text(encoding='utf-8'), content)

    def test_write_mode_rejects_incompatible_options_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / 'doc.md', 845)
            for options in (
                ('--json',), ('--ci',), ('--changed-only',), ('--staged',),
                ('--base-ref', 'HEAD'), ('--version',), ('--skill-path',),
                ('--create-loc-baseline',), ('--update-markdown-baseline',),
                ('--count-blank-lines',), ('--exclude', '*.md'), ('doctor',),
            ):
                with self.subTest(options=options):
                    result = self.run_guard(root, *options, '--create-markdown-baseline')
                    self.assertEqual((result.returncode, result.stdout), (3, ''))
                    self.assertFalse((root / BASELINE).exists())

    def test_symlinks_and_outside_scope_cannot_gain_an_allowance(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as other:
            root, outside = Path(temp), Path(other)
            init_git(root)
            write_lines(root / 'doc.md', 845)
            write_lines(outside / 'outside.md', 845)
            self.assertEqual(self.run_guard(root, str(outside), '--create-markdown-baseline').returncode, 3)
            try:
                (root / 'alias.md').symlink_to(root / 'doc.md')
            except OSError:
                self.skipTest('file symlinks unavailable')
            self.assertEqual(self.run_guard(root, '.', '--create-markdown-baseline').returncode, 0)
            self.assertEqual(self.run_guard(root, 'alias.md', '--json').returncode, 1)
            self.assertEqual(self.run_guard(root, 'doc.md', '--json').returncode, 0)
            self.assertEqual(self.run_guard(root, str(outside), '--json').returncode, 3)
            (root / 'doc.md').unlink()
            (root / 'doc.md').symlink_to(outside / 'outside.md')
            before = (root / BASELINE).read_bytes()
            for mode in ('--json', '--update-markdown-baseline'):
                self.assertEqual(self.run_guard(root, '.', mode).returncode, 3)
                self.assertEqual((root / BASELINE).read_bytes(), before)
