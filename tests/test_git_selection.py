from __future__ import annotations

import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase, git, init_git, write_config, write_lines


class GitSelectionTests(CodeGuardTestCase):
    def test_changed_only_intersects_git_candidates_with_positional_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            for name in ["src/a.py", "src/b.py", "tests/test_a.py", "docs/readme.md", "unchanged.py"]:
                write_lines(root / name, 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "src/a.py", 4); write_lines(root / "src/b.py", 4)

            cases = [
                ((".",), {"src/a.py", "src/b.py"}),
                (("src/a.py",), {"src/a.py"}),
                (("unchanged.py",), set()),
                (("src",), {"src/a.py", "src/b.py"}),
                (("./src",), {"src/a.py", "src/b.py"}),
                ((str((root / "src").resolve()),), {"src/a.py", "src/b.py"}),
                (("tests",), set()),
                (("src/a.py", "src/b.py"), {"src/a.py", "src/b.py"}),
                (("src", "tests"), {"src/a.py", "src/b.py"}),
                (("src/a.py", "tests"), {"src/a.py"}),
            ]
            for bounds, expected in cases:
                with self.subTest(bounds=bounds):
                    result = self.run_guard(root, *bounds, "--changed-only", "--warn", "3", "--fail", "6", "--json")
                    self.assertEqual({item["path"] for item in self.findings(result)}, expected)
                    if not expected:
                        self.assertEqual((result.returncode, self.read_json(result)["overall"]), (0, "pass"))

    def test_changed_only_normalizes_deduplicates_and_resolves_from_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            write_lines(root / "src/a.py", 1); write_lines(root / "other.py", 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "src/a.py", 4); write_lines(root / "other.py", 4)

            equivalent = self.run_guard(
                root, "./src/a.py", "src/../src/a.py", str((root / "src/a.py").resolve()),
                "--changed-only", "--warn", "3", "--fail", "6", "--json",
            )
            self.assertEqual([item["path"] for item in self.findings(equivalent)], ["src/a.py"])
            from_subdirectory = self.run_guard(
                root / "src", ".", "--changed-only", "--warn", "3", "--fail", "6", "--json",
            )
            self.assertEqual([item["path"] for item in self.findings(from_subdirectory)], ["src/a.py"])

    def test_changed_only_directory_bound_uses_path_containment_not_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            write_lines(root / "src/app/a.py", 1); write_lines(root / "src/application-other/b.py", 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "src/app/a.py", 4); write_lines(root / "src/application-other/b.py", 4)

            result = self.run_guard(root, "src/app", "--changed-only", "--warn", "3", "--fail", "6", "--json")
            self.assertEqual([item["path"] for item in self.findings(result)], ["src/app/a.py"])

    def test_changed_only_unions_multiple_directory_bounds_before_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            for name in ["src/a.py", "tests/test_a.py", "docs/unrelated.py"]:
                write_lines(root / name, 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            for name in ["src/a.py", "tests/test_a.py", "docs/unrelated.py"]:
                write_lines(root / name, 4)

            result = self.run_guard(root, "src", "tests", "--changed-only", "--warn", "3", "--fail", "6", "--json")
            self.assertEqual({item["path"] for item in self.findings(result)}, {"src/a.py", "tests/test_a.py"})

    def test_changed_only_validates_missing_and_does_not_broaden_external_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp); init_git(root)
            write_lines(root / "other.py", 1); git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "other.py", 4)
            outside = Path(outside_temp) / "outside.py"; write_lines(outside, 4)

            missing = self.run_guard(root, "missing.py", "--changed-only", "--json")
            self.assertEqual(missing.returncode, 3)
            self.assertIn("explicit path does not exist: missing.py", self.read_json(missing)["error"])
            external = self.run_guard(root, str(outside), "--changed-only", "--warn", "3", "--fail", "6", "--json")
            self.assertEqual((external.returncode, self.read_json(external)["overall"], self.findings(external)), (0, "pass", []))

    def test_changed_only_exact_issue_46_regression_is_empty_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            write_lines(root / "narrow.py", 1); write_lines(root / "other.py", 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "other.py", 75)
            result = self.run_guard(root, "narrow.py", "--changed-only", "--warn", "50", "--fail", "100", "--json")
            self.assertEqual((result.returncode, self.read_json(result)["overall"], self.findings(result)), (0, "pass", []))

    def test_scope_exclude_applies_after_changed_bound_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            write_lines(root / "src/a.py", 1); write_lines(root / "src/b.py", 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "src/a.py", 4); write_lines(root / "src/b.py", 4)
            result = self.run_guard(
                root, "src/a.py", "--changed-only", "--scope-exclude", "src/a.py",
                "--warn", "3", "--fail", "6", "--json",
            )
            self.assertEqual((result.returncode, self.read_json(result)["overall"], self.findings(result)), (0, "pass", []))

    def test_staged_intersects_candidates_with_file_bounds_and_can_be_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            for name in ["src/a.py", "src/b.py", "unstaged.py", "unchanged.py"]:
                write_lines(root / name, 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "src/a.py", 4); write_lines(root / "src/b.py", 4)
            git(root, "add", "src/a.py", "src/b.py")
            write_lines(root / "unstaged.py", 4)

            bounded = self.run_guard(root, "src/a.py", "--staged", "--warn", "3", "--fail", "6", "--json")
            self.assertEqual([item["path"] for item in self.findings(bounded)], ["src/a.py"])
            empty = self.run_guard(root, "unchanged.py", "--staged", "--json")
            self.assertEqual((empty.returncode, self.read_json(empty)["overall"], self.findings(empty)), (0, "pass", []))

    def test_base_ref_intersects_candidates_with_subtree_file_and_empty_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            for name in ["src/a.py", "src/b.py", "docs/spec.md", "tests/unchanged.py", "legacy.py"]:
                write_lines(root / name, 1 if name != "legacy.py" else 7)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            base = git(root, "rev-parse", "HEAD").stdout.strip()
            write_lines(root / "src/a.py", 4); write_lines(root / "src/b.py", 4); write_lines(root / "docs/spec.md", 801)
            git(root, "add", "."); git(root, "commit", "-m", "feature")

            subtree = self.run_guard(root, "src", "--base-ref", base, "--warn", "3", "--fail", "6", "--json")
            self.assertEqual({item["path"] for item in self.findings(subtree)}, {"src/a.py", "src/b.py"})
            file_bound = self.run_guard(root, "docs/spec.md", "--base-ref", base, "--json")
            self.assertEqual(
                [item["path"] for item in self.read_json(file_bound)["guards"]["markdownDocumentSize"]["findings"]],
                ["docs/spec.md"],
            )
            empty = self.run_guard(root, "tests", "--base-ref", base, "--json")
            self.assertEqual((empty.returncode, self.read_json(empty)["overall"], self.findings(empty)), (0, "pass", []))

    def test_git_modes_fail_cleanly_without_git_even_when_loc_is_disabled(self) -> None:
        modes = [("--changed-only",), ("--staged",), ("--base-ref", "main")]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = write_config(root, {"enabled": False})
            for mode in modes:
                with self.subTest(mode=mode):
                    result = self.run_guard(root, ".", *mode, "--config", str(config), "--json")
                    self.assertEqual(result.returncode, 3)
                    self.assertEqual(self.read_json(result), {"error": "Git file-selection mode requires a Git repository"})

    def test_disabled_loc_does_not_bypass_conflicting_selection_modes(self) -> None:
        combinations = [
            ("--changed-only", "--staged"),
            ("--changed-only", "--base-ref", "HEAD"),
            ("--staged", "--base-ref", "HEAD"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = write_config(root, {"enabled": False})
            for arguments in combinations:
                with self.subTest(arguments=arguments):
                    result = self.run_guard(root, ".", *arguments, "--config", str(config), "--json")
                    self.assertEqual(result.returncode, 3)
                    self.assertIn("use only one file-selection mode", self.read_json(result)["error"])

    def test_disabled_loc_does_not_bypass_empty_base_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = write_config(root, {"enabled": False})
            for base_ref in ["", "   "]:
                with self.subTest(base_ref=base_ref):
                    result = self.run_guard(root, ".", "--base-ref", base_ref, "--config", str(config), "--json")
                    self.assertEqual(result.returncode, 3)
                    self.assertIn("--base-ref must not be empty", self.read_json(result)["error"])

    def test_disabled_loc_does_not_bypass_unresolvable_base_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / "sample.py", 1)
            git(root, "add", ".")
            git(root, "commit", "-m", "baseline")
            config = write_config(root, {"enabled": False})
            result = self.run_guard(root, ".", "--base-ref", "missing-ref", "--config", str(config), "--json")
            self.assertEqual(result.returncode, 3)
            self.assertIn("unable to compare base ref 'missing-ref' with HEAD", self.read_json(result)["error"])

    def test_changed_only_includes_staged_unstaged_untracked_and_ignores_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            for name in ["staged.py", "unstaged.py", "deleted.py", "unchanged.py"]:
                write_lines(root / name, 1)
            git(root, "add", ".")
            git(root, "commit", "-m", "baseline")
            write_lines(root / "staged.py", 4); git(root, "add", "staged.py")
            write_lines(root / "unstaged.py", 4)
            (root / "deleted.py").unlink()
            write_lines(root / "untracked.py", 4)
            result = self.run_guard(root, ".", "--changed-only", "--warn", "3", "--fail", "6", "--json")
            self.assertEqual({item["path"] for item in self.findings(result)}, {"staged.py", "unstaged.py", "untracked.py"})

    def test_staged_excludes_unstaged_and_untracked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            write_lines(root / "staged.py", 1); write_lines(root / "unstaged.py", 1)
            git(root, "add", "."); git(root, "commit", "-m", "baseline")
            write_lines(root / "staged.py", 4); git(root, "add", "staged.py")
            write_lines(root / "unstaged.py", 4); write_lines(root / "untracked.py", 4)
            result = self.run_guard(root, ".", "--staged", "--json")
            self.assertEqual([item["path"] for item in self.findings(result)], ["staged.py"])

    def test_base_ref_detects_committed_acmr_only_and_invalid_ref_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            write_lines(root / "changed.py", 1); write_lines(root / "deleted.py", 1); write_lines(root / "legacy.py", 7)
            git(root, "add", "."); git(root, "commit", "-m", "base"); base = git(root, "rev-parse", "HEAD").stdout.strip()
            write_lines(root / "changed.py", 7); write_lines(root / "added.py", 7); (root / "deleted.py").unlink()
            git(root, "add", "-A"); git(root, "commit", "-m", "feature")
            result = self.run_guard(root, ".", "--base-ref", base, "--warn", "3", "--fail", "6", "--json")
            self.assertEqual({item["path"] for item in self.findings(result)}, {"added.py", "changed.py"})
            self.assertEqual(self.run_guard(root, ".", "--base-ref", "missing-ref", "--json").returncode, 3)

    def test_base_ref_uses_merge_base_after_base_advances(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            write_lines(root / "base.py", 1); git(root, "add", "."); git(root, "commit", "-m", "base")
            git(root, "branch", "feature")
            write_lines(root / "base-only.py", 7); git(root, "add", "."); git(root, "commit", "-m", "base advance")
            git(root, "switch", "feature"); write_lines(root / "feature.py", 7); git(root, "add", "."); git(root, "commit", "-m", "feature")
            result = self.run_guard(root, ".", "--base-ref", "main", "--warn", "3", "--fail", "6", "--json")
            self.assertEqual([item["path"] for item in self.findings(result)], ["feature.py"])
