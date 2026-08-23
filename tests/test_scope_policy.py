from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from helpers import CodeGuardTestCase, git, init_git, write_config, write_lines

from agent_code_guard.file_selection import resolve_scope


def selection_args(*paths: str, config: Path | None = None, scope_exclude: list[str] | None = None, **modes: object) -> SimpleNamespace:
    return SimpleNamespace(
        paths=list(paths) or ["."],
        changed_only=modes.get("changed_only", False),
        staged=modes.get("staged", False),
        base_ref=modes.get("base_ref"),
        config=str(config) if config else None,
        scope_exclude=scope_exclude or [],
    )


class ScopePolicyTests(CodeGuardTestCase):
    def test_scope_schema_and_additive_cli_exclusions(self) -> None:
        invalid = [
            {"scope": []}, {"scope": "x"}, {"scope": {"exclude": {}}},
            {"scope": {"exclude": "foo"}}, {"scope": {"exclude": [None]}},
            {"scope": {"exclude": [1]}}, {"scope": {"exclude": [{}]}},
            {"scope": {"exclude": [""]}}, {"scope": {"exclude": ["   "]}},
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "keep.py", 1)
            write_lines(root / "vendor" / "drop.py", 1)
            write_lines(root / "generated" / "drop.py", 1)
            for index, document in enumerate(invalid):
                config = root / f"invalid-{index}.json"
                config.write_text(json.dumps(document), encoding="utf-8")
                with self.subTest(document=document):
                    result = self.run_guard(root, ".", "--config", str(config), "--json")
                    self.assertEqual(result.returncode, 3)
                    self.assertIn("scope", self.read_json(result)["error"])
            for scope in [None, {}, {"exclude": []}]:
                config = root / "valid.json"
                config.write_text(json.dumps({} if scope is None else {"scope": scope}), encoding="utf-8")
                resolved = resolve_scope(selection_args(".", config=config), root)
                self.assertIn((root / "keep.py").resolve(), resolved.files)
            config = root / "combined.json"
            config.write_text(json.dumps({"scope": {"exclude": ["vendor/**"]}}), encoding="utf-8")
            resolved = resolve_scope(selection_args(".", config=config, scope_exclude=["generated/**"]), root)
            self.assertIn((root / "keep.py").resolve(), resolved.files)
            self.assertNotIn((root / "vendor" / "drop.py").resolve(), resolved.files)
            self.assertNotIn((root / "generated" / "drop.py").resolve(), resolved.files)

    def test_patterns_apply_to_explicit_git_and_external_files_and_can_empty_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as external_temp:
            root = Path(temp); init_git(root)
            source = root / "nested" / "sample.py"; write_lines(source, 1)
            external = Path(external_temp) / "outside.py"; write_lines(external, 1)
            git(root, "add", "."); git(root, "commit", "-m", "base")
            write_lines(source, 2)
            patterns = ["nested\\**", external.resolve().as_posix()]
            config = root / "scope.json"
            config.write_text(json.dumps({"scope": {"exclude": patterns}}), encoding="utf-8")
            git(root, "add", "scope.json"); git(root, "commit", "-m", "config")
            self.assertEqual(resolve_scope(selection_args(str(source), config=config), root).files, ())
            self.assertEqual(resolve_scope(selection_args(str(external), config=config), root).files, ())
            self.assertEqual(resolve_scope(selection_args(".", config=config, changed_only=True), root).files, ())

    def test_recursive_git_enumeration_uses_standard_ignores_and_keeps_tracked_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            for name in ["tracked.py", "tracked-but-now-ignored.py"]:
                write_lines(root / name, 1)
            git(root, "add", "."); git(root, "commit", "-m", "base")
            write_lines(root / "normal.py", 1)
            write_lines(root / "ignored.py", 1)
            write_lines(root / "nested" / "ignored.py", 1)
            write_lines(root / "ignored-directory" / "ignored.py", 1)
            write_lines(root / "sp ace" / "Δ.py", 1)
            write_lines(root / "info-ignored.py", 1)
            (root / ".gitignore").write_text(
                "ignored.py\ntracked-but-now-ignored.py\nignored-directory/\n", encoding="utf-8"
            )
            (root / "nested" / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
            (root / ".git" / "info" / "exclude").write_text("info-ignored.py\n", encoding="utf-8")
            resolved = resolve_scope(selection_args("."), root)
            relative = {path.relative_to(resolved.root).as_posix() for path in resolved.files}
            self.assertTrue({"tracked.py", "tracked-but-now-ignored.py", "normal.py", "sp ace/Δ.py"} <= relative)
            self.assertTrue({"ignored.py", "nested/ignored.py", "info-ignored.py"}.isdisjoint(relative))
            self.assertEqual(resolve_scope(selection_args("ignored.py"), root).files, ((root / "ignored.py").resolve(),))
            self.assertEqual(resolve_scope(selection_args("nested"), root).files, ((root / "nested" / ".gitignore").resolve(),))
            self.assertEqual(resolve_scope(selection_args("ignored-directory"), root).files, ())
            self.assertEqual(resolve_scope(selection_args("sp ace"), root).files, ((root / "sp ace" / "Δ.py").resolve(),))

    def test_scope_exclusion_applies_after_changed_staged_and_base_ref_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); init_git(root)
            source = root / "generated" / "changed.py"; write_lines(source, 1)
            config = root / "scope.json"
            config.write_text(json.dumps({"scope": {"exclude": ["generated/**"]}}), encoding="utf-8")
            git(root, "add", "."); git(root, "commit", "-m", "base")
            base = git(root, "rev-parse", "HEAD").stdout.strip()
            write_lines(source, 2); git(root, "add", "generated/changed.py")
            self.assertEqual(resolve_scope(selection_args(".", config=config, changed_only=True), root).files, ())
            self.assertEqual(resolve_scope(selection_args(".", config=config, staged=True), root).files, ())
            git(root, "commit", "-m", "change")
            self.assertEqual(resolve_scope(selection_args(".", config=config, base_ref=base), root).files, ())

    def test_recursive_builtin_pruning_does_not_override_explicit_file_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            builtins = [".git", "node_modules", "bin", "obj"]
            for directory in builtins:
                write_lines(root / directory / "special.py", 1)
            write_lines(root / "normal.py", 1)
            recursive = resolve_scope(selection_args("."), root)
            self.assertEqual(recursive.files, ((root / "normal.py").resolve(),))
            explicit = resolve_scope(selection_args("bin/special.py"), root)
            self.assertEqual(explicit.files, ((root / "bin" / "special.py").resolve(),))

    def test_no_vcs_directory_scope_uses_walk_and_global_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "src" / "keep.py", 1)
            write_lines(root / "vendor" / "drop.py", 1)
            config = root / "config.json"
            config.write_text(json.dumps({"scope": {"exclude": ["vendor/**"]}}), encoding="utf-8")
            resolved = resolve_scope(selection_args(".", config=config), root)
            self.assertIn((root / "src" / "keep.py").resolve(), resolved.files)
            self.assertNotIn((root / "vendor" / "drop.py").resolve(), resolved.files)

    def test_global_exclusion_precedes_analysis_and_loc_exclusion_remains_loc_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            broken = root / "broken.py"; broken.write_text("def broken(:\n", encoding="utf-8")
            global_config = write_config(root, {}, scope={"exclude": ["broken.py"]})
            result = self.run_guard(root, "broken.py", "--config", str(global_config), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.read_json(result)["overall"], "pass")

            sample = root / "generated" / "sample.py"
            sample.parent.mkdir(); sample.write_text("def f():\n    return 1\n", encoding="utf-8")
            loc_only = write_config(root, {"exclude": ["generated/**"]})
            loc_result = self.run_guard(root, "generated/sample.py", "--config", str(loc_only), "--json")
            payload = self.read_json(loc_result)
            self.assertEqual(payload["guards"]["loc"]["findings"], [])
            self.assertEqual(len(payload["guards"]["callableSize"]["findings"]), 1)
            global_only = write_config(root, {}, scope={"exclude": ["generated/**"]})
            global_result = self.run_guard(root, "generated/sample.py", "--config", str(global_only), "--json")
            self.assertTrue(all(not guard["findings"] for guard in self.read_json(global_result)["guards"].values()))

    def test_cli_help_distinguishes_global_and_loc_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_guard(Path(temp), "--help")
            self.assertIn("--scope-exclude", result.stdout)
            self.assertIn("All-guards", result.stdout)
            self.assertIn("LOC-only", result.stdout)


if __name__ == "__main__":
    import unittest
    unittest.main()
