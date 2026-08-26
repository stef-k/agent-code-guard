from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.helpers import CODE_GUARD, CodeGuardTestCase, write_config, write_lines


class LocParityTests(CodeGuardTestCase):
    def test_default_parses_malformed_source_but_explicit_syntax_disable_is_loc_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CODE_GUARD), "broken.py", "--json"],
                cwd=root, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            config = write_config(root, {}, guards={
                "loc": {}, "callableSize": {"enabled": False}, "nesting": {"enabled": False},
                "cyclomaticComplexity": {"enabled": False},
            })
            result = subprocess.run(
                [sys.executable, str(CODE_GUARD), "broken.py", "--config", str(config), "--json"],
                cwd=root, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["guards"]["loc"]["findings"][0]["countedLoc"], 1)

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
