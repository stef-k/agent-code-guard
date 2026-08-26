from __future__ import annotations

import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase, git, init_git, write_lines


class SymlinkScopeTests(CodeGuardTestCase):
    def make_symlink(self, link: Path, target: Path, *, target_is_directory: bool = False) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(target, target_is_directory=target_is_directory)
        except OSError as exc:
            self.skipTest(f"symlink creation is unavailable: {exc}")

    def test_recursive_non_git_exact_issue_46_external_file_symlink_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "outside" / "outside.py", 11)
            self.make_symlink(root / "audit" / "filelink.py", Path("../outside/outside.py"))

            result = self.run_guard(root, "audit", "--warn", "5", "--fail", "10", "--json")

            self.assertEqual((result.returncode, self.read_json(result)["overall"]), (0, "pass"), result.stderr)
            self.assertEqual(self.findings(result), [])

    def test_recursive_non_git_internal_file_symlink_is_skipped_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "audit" / "real.py", 7)
            self.make_symlink(root / "audit" / "alias.py", Path("real.py"))

            result = self.run_guard(root, "audit", "--warn", "3", "--fail", "6", "--json")

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual([item["path"] for item in self.findings(result)], ["audit/real.py"])

    def test_recursive_directory_symlinks_are_not_traversed_including_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "audit" / "normal.py", 4)
            write_lines(root / "other-dir" / "outside.py", 7)
            self.make_symlink(root / "audit" / "linked-dir", Path("../other-dir"), target_is_directory=True)
            self.make_symlink(root / "audit" / "cycle", Path("."), target_is_directory=True)

            result = self.run_guard(root, "audit", "--warn", "3", "--fail", "6", "--json")

            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual([item["path"] for item in self.findings(result)], ["audit/normal.py"])

    def test_explicit_internal_and_external_file_symlinks_are_analyzed_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp)
            write_lines(root / "audit" / "real.py", 4)
            outside = Path(outside_temp) / "outside.py"
            write_lines(outside, 7)
            internal_link = root / "audit" / "internal.py"
            external_link = root / "audit" / "external.py"
            self.make_symlink(internal_link, Path("real.py"))
            self.make_symlink(external_link, outside)

            internal = self.run_guard(
                root, "audit/real.py", "audit/internal.py", "--warn", "3", "--fail", "6", "--json",
            )
            external = self.run_guard(root, "audit/external.py", "--warn", "3", "--fail", "6", "--json")

            self.assertEqual(internal.returncode, 1, internal.stderr)
            self.assertEqual([item["path"] for item in self.findings(internal)], ["audit/real.py"])
            self.assertEqual(external.returncode, 2, external.stderr)
            self.assertEqual([item["countedLoc"] for item in self.findings(external)], [7])

    def test_explicit_directory_symlink_is_a_scope_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "target" / "sample.py", 4)
            self.make_symlink(root / "linked-dir", Path("target"), target_is_directory=True)

            result = self.run_guard(root, "linked-dir", "--json")

            self.assertEqual(result.returncode, 3)
            self.assertIn("explicit directory symlink is not recursively traversed", self.read_json(result)["error"])

    def test_broken_symlink_is_skipped_recursively_but_errors_when_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "audit" / "normal.py", 2)
            broken = root / "audit" / "broken.py"
            self.make_symlink(broken, Path("missing.py"))

            recursive = self.run_guard(root, "audit", "--json")
            explicit = self.run_guard(root, "audit/broken.py", "--json")

            self.assertEqual(recursive.returncode, 0, recursive.stderr)
            self.assertEqual([item["path"] for item in self.findings(recursive)], ["audit/normal.py"])
            self.assertEqual(explicit.returncode, 3)
            self.assertIn("explicit path does not exist: audit/broken.py", self.read_json(explicit)["error"])

    def test_git_backed_recursive_symlinks_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp); init_git(root)
            outside = Path(outside_temp) / "outside.py"
            write_lines(outside, 7)
            write_lines(root / "audit" / "normal.py", 4)
            write_lines(root / "other-dir" / "other.py", 7)
            self.make_symlink(root / "audit" / "internal.py", Path("normal.py"))
            self.make_symlink(root / "audit" / "external.py", outside)
            self.make_symlink(root / "audit" / "linked-dir", Path("../other-dir"), target_is_directory=True)
            git(root, "add", "."); git(root, "commit", "-m", "tracked symlink fixture")

            result = self.run_guard(root, "audit", "--warn", "3", "--fail", "6", "--json")

            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual([item["path"] for item in self.findings(result)], ["audit/normal.py"])

    def test_changed_only_directory_bound_remains_git_candidate_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            write_lines(root / "audit" / "unchanged.py", 7)
            write_lines(root / "audit" / "changed.py", 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "audit" / "changed.py", 4)

            result = self.run_guard(root, "audit", "--changed-only", "--warn", "3", "--fail", "6", "--json")

            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual([item["path"] for item in self.findings(result)], ["audit/changed.py"])
