from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from tests.helpers import CodeGuardTestCase, write_lines

from agent_code_guard.file_selection import resolve_scope


class ExplicitScopeTests(CodeGuardTestCase):
    def test_one_explicit_file_works_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "sample.py", 4)
            result = self.run_guard(root, "sample.py", "--warn", "3", "--fail", "6", "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual([item["path"] for item in self.findings(result)], ["sample.py"])

    def test_multiple_explicit_files_work_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ["a.py", "b.kt", "c.ts"]:
                write_lines(root / name, 2)
            result = self.run_guard(root, "a.py", "b.kt", "c.ts", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({item["path"] for item in self.findings(result)}, {"a.py", "b.kt", "c.ts"})

    def test_explicit_directory_and_dot_are_recursive_audits_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "src" / "nested" / "sample.py", 2)
            write_lines(root / "outside.ts", 2)
            directory = self.run_guard(root, "src", "--json")
            audit = self.run_guard(root, ".", "--json")
            self.assertEqual([item["path"] for item in self.findings(directory)], ["src/nested/sample.py"])
            self.assertEqual({item["path"] for item in self.findings(audit)}, {"src/nested/sample.py", "outside.ts"})

    def test_missing_explicit_path_is_a_scope_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_guard(Path(temp), "missing.py", "--json")
            self.assertEqual(result.returncode, 3)
            self.assertIn("explicit path does not exist: missing.py", self.read_json(result)["error"])

    def test_unsupported_explicit_file_is_valid_but_not_applicable_to_loc(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "A.py", 2)
            (root / "notes.txt").write_text("notes\n", encoding="utf-8")
            result = self.run_guard(root, "A.py", "notes.txt", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([item["path"] for item in self.findings(result)], ["A.py"])

    def test_common_scope_preserves_files_before_guard_applicability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "Foo.py", 1)
            (root / "artifact.custom").write_text("future guard input\n", encoding="utf-8")
            args = SimpleNamespace(
                paths=["Foo.py", "artifact.custom"], changed_only=False, staged=False, base_ref=None,
            )
            scope = resolve_scope(args, root)
            self.assertEqual(scope.root, root.resolve())
            self.assertEqual(scope.files, ((root / "Foo.py").resolve(), (root / "artifact.custom").resolve()))
