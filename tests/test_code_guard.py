from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from helpers import CODE_GUARD, CodeGuardTestCase, git, init_git, write_config, write_lines

sys.path.insert(0, str(CODE_GUARD.parent))
from file_selection import SelectionArgs, resolve_scope


class ResultContractTests(CodeGuardTestCase):
    def test_pass_review_fail_and_policy_routing(self) -> None:
        cases = [(2, "pass", "ok", 0, []), (4, "review", "warn", 1, ["loc"]), (7, "fail", "fail", 2, ["loc"])]
        for lines, overall, native, code, policies in cases:
            with self.subTest(overall=overall), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                write_lines(root / "sample.py", lines)
                result = self.run_guard(root, ".", "--warn", "3", "--fail", "6", "--json")
                data = self.read_json(result)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(data["overall"], overall)
                self.assertEqual(data["requiredPolicies"], policies)
                self.assertEqual(data["guards"]["loc"]["findings"][0]["nativeStatus"], native)

    def test_exemption_is_pass_with_native_metadata_and_no_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "large.py", 7)
            config = write_config(root, {"warnAt": 3, "failAt": 6, "allowedLargeFiles": [{"path": "large.py", "reason": "Approved cohesive module."}]})
            result = self.run_guard(root, ".", "--config", str(config), "--json")
            finding = self.findings(result)[0]
            self.assertEqual((result.returncode, self.read_json(result)["overall"]), (0, "pass"))
            self.assertEqual(self.read_json(result)["requiredPolicies"], [])
            self.assertEqual((finding["state"], finding["nativeStatus"], finding["reason"]), ("pass", "exempt", "Approved cohesive module."))

    def test_ci_changes_only_review_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "review.py", 4)
            self.assertEqual(self.run_guard(root, ".", "--warn", "3", "--fail", "6", "--ci").returncode, 0)
            write_lines(root / "review.py", 7)
            self.assertEqual(self.run_guard(root, ".", "--warn", "3", "--fail", "6", "--ci").returncode, 2)
            config = write_config(root, {"overrides": [{"match": ["*.py"], "warnAt": True, "failAt": 6}]})
            self.assertEqual(self.run_guard(root, ".", "--config", str(config), "--ci", "--json").returncode, 3)

    def test_disabled_loc_has_no_findings_or_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "large.py", 700)
            config = write_config(root, {"enabled": False})
            result = self.run_guard(root, ".", "--config", str(config), "--json")
            self.assertEqual(self.read_json(result), {"overall": "pass", "requiredPolicies": [], "guards": {"loc": {"state": "pass", "findings": []}}})


class LocParityTests(CodeGuardTestCase):
    def test_extensions_comments_php_attribute_and_unknown_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Main.kt").write_text("// comment\nval x = 1\n", encoding="utf-8")
            (root / "script.rb").write_text("# comment\nx = 1\n", encoding="utf-8")
            (root / "Controller.php").write_text("# comment\n#[Route('/')]\nclass C {}\n", encoding="utf-8")
            write_lines(root / "App.swift", 1)
            write_lines(root / "widget.vue", 1)
            write_lines(root / "ignored.unknown", 10)
            result = self.run_guard(root, ".", "--warn", "10", "--fail", "20", "--ignore-comment-lines", "--json")
            counts = {item["path"]: item["countedLoc"] for item in self.findings(result)}
            self.assertEqual(counts, {"App.swift": 1, "Controller.php": 2, "Main.kt": 1, "script.rb": 1, "widget.vue": 1})

    def test_blank_and_comment_count_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text("# comment\n\nvalue = 1\n", encoding="utf-8")
            default = self.run_guard(root, ".", "--json")
            configured = self.run_guard(root, ".", "--count-blank-lines", "--ignore-comment-lines", "--json")
            self.assertEqual(self.findings(default)[0]["countedLoc"], 2)
            self.assertEqual(self.findings(configured)[0]["countedLoc"], 2)

    def test_overrides_last_match_cli_globals_and_exemption_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "RootTest.kt", 10)
            write_lines(root / "src" / "NestedTest.kt", 10)
            write_lines(root / "other.ts", 7)
            config = write_config(root, {
                "warnAt": 3, "failAt": 6,
                "overrides": [
                    {"match": ["**/*Test.kt"], "warnAt": 6, "failAt": 9},
                    {"match": ["RootTest.kt", "src/**"], "warnAt": 9, "failAt": 12},
                ],
                "allowedLargeFiles": [{"path": "src/NestedTest.kt", "reason": "Approved fixture."}],
            })
            result = self.run_guard(root, ".", "--config", str(config), "--warn", "10", "--fail", "20", "--json")
            files = {item["path"]: item for item in self.findings(result)}
            self.assertEqual((files["RootTest.kt"]["overrideIndex"], files["RootTest.kt"]["warnAt"], files["RootTest.kt"]["nativeStatus"]), (1, 9, "warn"))
            self.assertEqual((files["src/NestedTest.kt"]["overrideIndex"], files["src/NestedTest.kt"]["nativeStatus"], files["src/NestedTest.kt"]["reason"]), (1, "exempt", "Approved fixture."))
            self.assertEqual((files["other.ts"]["warnAt"], files["other.ts"]["failAt"], files["other.ts"]["nativeStatus"]), (10, 20, "ok"))

    def test_root_nested_exclusions_project_pattern_and_literal_metacharacters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ["generated/root.py", "src/generated/nested.py", "project/local.py", "keep.py"]:
                write_lines(root / name, 7)
            write_lines(root / "file[1].py", 7)
            config = write_config(root, {
                "warnAt": 3, "failAt": 6,
                "exclude": ["**/generated/**", "project/**", "file[1].py"],
            })
            result = self.run_guard(root, ".", "--config", str(config), "--json")
            self.assertEqual([item["path"] for item in self.findings(result)], ["keep.py"])

    def test_full_audit_sees_all_source_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "one.py", 2)
            write_lines(root / "two.kt", 2)
            result = self.run_guard(root, ".", "--json")
            self.assertEqual({item["path"] for item in self.findings(result)}, {"one.py", "two.kt"})


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
            args = SelectionArgs(["Foo.py", "artifact.custom"], False, False, None)
            scope = resolve_scope(args, root)
            self.assertEqual(scope.root, root.resolve())
            self.assertEqual(scope.files, ((root / "Foo.py").resolve(), (root / "artifact.custom").resolve()))


class ConfigurationValidationTests(CodeGuardTestCase):
    def test_global_thresholds_require_positive_json_integers(self) -> None:
        invalid_values = ["3", True, 3.0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for field in ["warnAt", "failAt"]:
                for value in invalid_values:
                    with self.subTest(field=field, value=value):
                        loc = {"warnAt": 3, "failAt": 6, field: value}
                        config = write_config(root, loc)
                        result = self.run_guard(root, ".", "--config", str(config), "--json")
                        self.assertEqual(result.returncode, 3)
                        self.assertIn(f"guards.loc.{field} must be a positive integer", self.read_json(result)["error"])

    def test_positive_integer_global_thresholds_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "sample.py", 4)
            config = write_config(root, {"warnAt": 3, "failAt": 6})
            result = self.run_guard(root, ".", "--config", str(config), "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(self.findings(result)[0]["nativeStatus"], "warn")

    def test_malformed_exemptions_are_errors(self) -> None:
        entries = [None, {}, {"path": ""}, {"path": "x.py", "reason": ""}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for entry in entries:
                with self.subTest(entry=entry):
                    config = write_config(root, {"allowedLargeFiles": [entry]})
                    self.assertEqual(self.run_guard(root, ".", "--config", str(config), "--json").returncode, 3)

    def test_malformed_overrides_are_errors(self) -> None:
        entries = [{}, {"match": [], "warnAt": 3, "failAt": 6}, {"match": ["*.py"], "warnAt": True, "failAt": 6}, {"match": ["*.py"], "warnAt": 6, "failAt": 6}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for entry in entries:
                with self.subTest(entry=entry):
                    config = write_config(root, {"overrides": [entry]})
                    self.assertEqual(self.run_guard(root, ".", "--config", str(config), "--json").returncode, 3)

    def test_malformed_top_level_structures_are_errors(self) -> None:
        documents = [[], {"guards": []}, {"guards": {"loc": []}}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, document in enumerate(documents):
                path = root / f"bad-{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                self.assertEqual(self.run_guard(root, ".", "--config", str(path), "--json").returncode, 3)


class GitSelectionTests(CodeGuardTestCase):
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


if __name__ == "__main__":
    import unittest
    unittest.main()
