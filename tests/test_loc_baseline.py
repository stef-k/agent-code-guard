from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from tests.helpers import CodeGuardTestCase, init_git, write_config, write_lines


BASELINE = Path(".agent-tools/code-guard.loc-baseline.json")


class LocBaselineTests(CodeGuardTestCase):
    def test_normal_analysis_ratchet_states_and_output_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            for name, lines in {
                "boundary.py": 7,
                "reduced.py": 6,
                "grown.py": 8,
                "new.py": 7,
                "small.py": 3,
            }.items():
                write_lines(root / name, lines)
            baseline = root / BASELINE
            baseline.parent.mkdir()
            baseline.write_text(json.dumps({
                "version": 1,
                "loc": {"files": [
                    {"path": "boundary.py", "allowedLoc": 7},
                    {"path": "grown.py", "allowedLoc": 7},
                    {"path": "reduced.py", "allowedLoc": 7},
                    {"path": "small.py", "allowedLoc": 7},
                ]},
            }, indent=2) + "\n", encoding="utf-8", newline="\n")
            (root / "nested.py").write_text(
                "def nested(value):\n    if value:\n        if value > 1:\n            return value\n",
                encoding="utf-8",
            )
            (baseline.parent / "code-guard.config.json").write_text(json.dumps({
                "version": 1,
                "guards": {"nesting": {"reviewAt": 1}},
            }), encoding="utf-8")

            full = self.run_guard(root, ".", "--warn", "3", "--fail", "5", "--json")
            self.assertEqual(full.returncode, 2)
            data = self.read_json(full)
            findings = {item["path"]: item for item in data["guards"]["loc"]["findings"]}
            self.assertEqual(
                (findings["boundary.py"]["state"], findings["boundary.py"]["nativeStatus"],
                 findings["boundary.py"]["baselineLoc"], findings["boundary.py"]["ratchetStatus"]),
                ("review", "grandfathered", 7, "within"),
            )
            self.assertEqual(findings["reduced.py"]["nativeStatus"], "grandfathered")
            self.assertEqual(findings["grown.py"]["nativeStatus"], "ratchetExceeded")
            self.assertEqual(findings["new.py"]["nativeStatus"], "fail")
            self.assertEqual(
                (findings["small.py"]["nativeStatus"], findings["small.py"]["ratchetStatus"]),
                ("ok", "notNeeded"),
            )
            self.assertEqual(data["overall"], "fail")
            self.assertIn("loc", data["requiredPolicies"])
            self.assertEqual(data["guards"]["nesting"]["state"], "review")
            self.assertIn("nesting", data["requiredPolicies"])

            compact = self.run_guard(
                root, ".", "--warn", "3", "--fail", "5", "--json", "--json-mode", "compact",
            )
            compact_paths = {item["path"] for item in self.findings(compact)}
            self.assertNotIn("small.py", compact_paths)
            self.assertIn("boundary.py", compact_paths)
            human = self.run_guard(root, "boundary.py", "--warn", "3", "--fail", "5")
            self.assertEqual(human.returncode, 1)
            self.assertIn("RATCHET: boundary.py — 7 LOC (warn 3, fail 5; baseline 7, within)\n", human.stdout)
            self.assertEqual(self.run_guard(root, "boundary.py", "--warn", "3", "--fail", "5", "--ci").returncode, 0)

    def test_create_and_update_lifecycle_is_non_increasing_and_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / "src" / "lower.py", 8)
            write_lines(root / "src" / "remove.py", 7)
            write_lines(root / "other" / "unchanged.py", 9)
            created = self.run_guard(root, ".", "--warn", "3", "--fail", "5", "--create-loc-baseline")
            self.assertEqual((created.returncode, created.stderr), (0, ""))
            self.assertEqual(created.stdout, "Created LOC baseline: .agent-tools/code-guard.loc-baseline.json (3 entries).\n")
            baseline = root / BASELINE
            original = baseline.read_bytes()
            self.assertTrue(original.endswith(b"\n"))
            self.assertEqual(self.run_guard(root, ".", "--create-loc-baseline").returncode, 3)

            write_lines(root / "src" / "lower.py", 7)
            write_lines(root / "src" / "remove.py", 5)
            partial = self.run_guard(root, "src", "--warn", "3", "--fail", "5", "--update-loc-baseline")
            self.assertEqual(partial.stdout, "Updated LOC baseline: .agent-tools/code-guard.loc-baseline.json (1 lowered, 1 removed, 0 unchanged).\n")
            entries = json.loads(baseline.read_text(encoding="utf-8"))["loc"]["files"]
            self.assertEqual(entries, [
                {"path": "other/unchanged.py", "allowedLoc": 9},
                {"path": "src/lower.py", "allowedLoc": 7},
            ])
            before_noop = baseline.stat().st_mtime_ns
            time.sleep(0.01)
            noop = self.run_guard(root, "src", "--warn", "3", "--fail", "5", "--update-loc-baseline")
            self.assertEqual(noop.stdout, "Updated LOC baseline: .agent-tools/code-guard.loc-baseline.json (0 lowered, 0 removed, 1 unchanged).\n")
            self.assertEqual(baseline.stat().st_mtime_ns, before_noop)

            write_lines(root / "src" / "lower.py", 8)
            before_growth = baseline.read_bytes()
            growth = self.run_guard(root, ".", "--warn", "3", "--fail", "5", "--update-loc-baseline")
            self.assertEqual((growth.returncode, growth.stdout), (3, ""))
            self.assertEqual(baseline.read_bytes(), before_growth)

            (root / "src" / "lower.py").rename(root / "src" / "renamed.py")
            renamed = self.run_guard(root, ".", "--warn", "3", "--fail", "5", "--update-loc-baseline")
            self.assertEqual(renamed.returncode, 0)
            self.assertNotIn("src/lower.py", baseline.read_text(encoding="utf-8"))
            analysis = self.run_guard(root, "src/renamed.py", "--warn", "3", "--fail", "5", "--json")
            self.assertEqual(self.findings(analysis)[0]["nativeStatus"], "fail")
            excluded = self.run_guard(
                root, "other", "--warn", "3", "--fail", "5",
                "--scope-exclude", "other/**", "--update-loc-baseline",
            )
            self.assertEqual(excluded.stdout, (
                "Updated LOC baseline: .agent-tools/code-guard.loc-baseline.json "
                "(0 lowered, 1 removed, 0 unchanged).\n"
            ))

    def test_invalid_baseline_schema_fails_closed_and_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / "legacy.py", 7)
            baseline = root / BASELINE
            baseline.parent.mkdir()
            baseline.write_text('{"version":1,"loc":{"files":[]},"unknown":true}\n', encoding="utf-8")
            before = baseline.read_bytes()
            invalid = self.run_guard(root, ".", "--json")
            self.assertEqual(invalid.returncode, 3)
            self.assertEqual(baseline.read_bytes(), before)

            baseline.write_text('{"version":1.0,"loc":{"files":[]}}\n', encoding="utf-8")
            wrong_version_type = baseline.read_bytes()
            invalid_version = self.run_guard(root, ".", "--json")
            self.assertEqual(invalid_version.returncode, 3)
            self.assertEqual(invalid_version.stderr, "")
            self.assertEqual(
                self.read_json(invalid_version),
                {"error": "LOC baseline version must be the integer 1"},
            )
            self.assertNotIn("guards", self.read_json(invalid_version))
            self.assertEqual(baseline.read_bytes(), wrong_version_type)

    def test_analysis_without_baseline_omits_ratchet_fields_and_never_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / "legacy.py", 7)
            baseline = root / BASELINE
            no_baseline = self.run_guard(root, ".", "--warn", "3", "--fail", "5", "--json")
            self.assertNotIn("baselineLoc", self.findings(no_baseline)[0])
            self.assertNotIn("ratchetStatus", self.findings(no_baseline)[0])
            self.assertFalse(baseline.exists())

            ordinary = self.run_guard(root, ".", "--warn", "3", "--fail", "5")
            self.assertEqual(ordinary.returncode, 2)
            self.assertFalse(baseline.exists())

    def test_create_rejects_scope_outside_analysis_root_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / "legacy.py", 7)
            baseline = root / BASELINE
            outside = Path(outside_temp) / "empty"
            outside.mkdir()
            escaped = self.run_guard(root, str(outside), "--create-loc-baseline")
            self.assertEqual(escaped.returncode, 3)
            self.assertFalse(baseline.exists())

    def test_create_rejects_incompatible_arguments_without_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / "legacy.py", 7)
            incompatible = self.run_guard(root, ".", "--create-loc-baseline", "--json")
            self.assertEqual((incompatible.returncode, incompatible.stdout), (3, ""))

    def test_fail_closed_and_analysis_never_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / "legacy.py", 7)
            baseline = root / BASELINE
            baseline.parent.mkdir()
            missing_target = Path(outside_temp) / "missing-baseline.json"
            try:
                baseline.symlink_to(missing_target)
            except OSError:
                self.skipTest("file symlinks are unavailable")
            self.assertTrue(baseline.is_symlink())
            dangling = self.run_guard(root, ".", "--json")
            self.assertEqual(dangling.returncode, 3)
            self.assertEqual(dangling.stderr, "")
            self.assertEqual(
                self.read_json(dangling),
                {"error": "LOC baseline path must not traverse a symlink or escape the analysis root"},
            )
            self.assertNotIn("guards", self.read_json(dangling))
            self.assertTrue(baseline.is_symlink())
            self.assertFalse(missing_target.exists())
            baseline.unlink()

            baseline.parent.mkdir(exist_ok=True)
            baseline.write_text(json.dumps({
                "version": 1,
                "loc": {"files": [{"path": "legacy.py", "allowedLoc": 7}]},
            }, indent=2) + "\n", encoding="utf-8")
            config = write_config(root, {
                "warnAt": 3,
                "failAt": 5,
                "allowedLargeFiles": [{"path": "*.py", "reason": "Reviewed exemption."}],
            })
            overlap = self.run_guard(root, ".", "--config", str(config), "--json")
            self.assertEqual(overlap.returncode, 3)
            self.assertIn("overlaps allowedLargeFiles", overlap.stdout)

        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp)
            outside = Path(outside_temp)
            init_git(root)
            write_lines(root / "legacy.py", 7)
            try:
                (root / "alias.py").symlink_to(root / "legacy.py")
            except OSError:
                self.skipTest("file symlinks are unavailable")
            direct_and_link = self.run_guard(
                root, "legacy.py", "alias.py", "--warn", "3", "--fail", "5",
                "--create-loc-baseline",
            )
            self.assertEqual(direct_and_link.returncode, 0)
            stored = json.loads((root / BASELINE).read_text(encoding="utf-8"))["loc"]["files"]
            self.assertEqual(stored, [{"path": "legacy.py", "allowedLoc": 7}])
            (root / BASELINE).unlink()
            (root / ".agent-tools").rmdir()
            try:
                (root / ".agent-tools").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("directory symlinks are unavailable")
            unsafe = self.run_guard(
                root, ".", "--warn", "3", "--fail", "5", "--create-loc-baseline",
            )
            self.assertEqual((unsafe.returncode, unsafe.stdout), (3, ""))
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
