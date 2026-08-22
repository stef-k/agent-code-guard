from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import CodeGuardTestCase, write_config

from agent_code_guard.analysis import analyze_files
from agent_code_guard.code_guard import run_guards
from agent_code_guard.file_selection import ResolvedScope
from agent_code_guard.guards import callable_size


def args(config: Path | None = None) -> SimpleNamespace:
    return SimpleNamespace(config=str(config) if config else None)


class CallableSizeConfigTests(unittest.TestCase):
    def write_document(self, root: Path, value: object) -> Path:
        path = root / "config.json"
        path.write_text(json.dumps({"guards": {"callableSize": value}}), encoding="utf-8")
        return path

    def test_omitted_and_explicit_false_are_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            omitted = root / "omitted.json"
            omitted.write_text("{}", encoding="utf-8")
            self.assertFalse(callable_size.load_config(args(omitted)).enabled)
            self.assertFalse(callable_size.load_config(args(self.write_document(root, {"enabled": False}))).enabled)

    def test_enabled_requires_positive_json_integer_review_at(self) -> None:
        invalid = [None, True, 1.5, "80", 0, -1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for value in invalid:
                section = {"enabled": True}
                if value is not None:
                    section["reviewAt"] = value
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "guards.callableSize.reviewAt must be a positive integer"):
                    callable_size.load_config(args(self.write_document(root, section)))


class CallableSizeEvaluationTests(unittest.TestCase):
    def test_javascript_assignment_and_anonymous_callback_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "owners.ts"
            source.write_text(
                "const assigned = (x: number) => x;\n"
                "function owner() { return [1].map((x) => x + 1); }\n",
                encoding="utf-8",
            )
            result = callable_size.run(root, callable_size.Config(True, 1), analyze_files([source]))
            identities = {finding.callable for finding in result.findings}
            self.assertIn("owners.assigned", identities)
            self.assertTrue(any("<callback@" in identity for identity in identities))

    def test_boundary_multiple_callables_and_no_fail(self) -> None:
        fixtures = Path(__file__).parent / "fixtures" / "analyzers"
        facts = analyze_files([fixtures / "php" / "Mixed.php"])
        result = callable_size.run(fixtures, callable_size.Config(True, 5), facts)
        by_name = {finding.callable: finding for finding in result.findings}
        self.assertEqual((by_name["Mixed.foo"].measured, by_name["Mixed.foo"].state), (6, "review"))
        self.assertEqual((by_name["Mixed.bar"].state, result.state), ("review", "review"))
        self.assertNotIn("fail", {finding.state for finding in result.findings})

    def test_exact_threshold_passes_and_next_line_reviews(self) -> None:
        fixtures = Path(__file__).parent / "fixtures" / "analyzers"
        facts = analyze_files([fixtures / "rust" / "second_wave.rs"])
        target = next(item for item in facts.callables if item.identity == "second_wave.evaluate")
        self.assertEqual(callable_size.evaluate(fixtures, callable_size.Config(True, 12), target).state, "pass")
        self.assertEqual(callable_size.evaluate(fixtures, callable_size.Config(True, 11), target).state, "review")

    def test_vue_preserves_original_range_path_and_embedded_language(self) -> None:
        fixtures = Path(__file__).parent / "fixtures" / "analyzers"
        facts = analyze_files([fixtures / "vue" / "Setup.vue"])
        finding = callable_size.run(fixtures, callable_size.Config(True, 1), facts).findings[0]
        self.assertEqual((finding.path, finding.start_line, finding.embedded_language), ("vue/Setup.vue", 8, "typescript"))


class CallableSizeOrchestrationTests(unittest.TestCase):
    def test_disabled_does_not_import_analysis_and_enabled_builds_facts_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.py"
            source.write_text("def sample():\n    return 1\n", encoding="utf-8")
            scope = ResolvedScope(root, (source,))
            disabled_args = SimpleNamespace(**vars(args()), warn=None, fail=None, include=[], exclude=[], count_blank_lines=False, ignore_comment_lines=False)
            with patch("agent_code_guard.code_guard.import_module") as loader:
                run_guards(scope, disabled_args)
                loader.assert_not_called()

            config = write_config(root, {"enabled": False}, guards={"callableSize": {"enabled": True, "reviewAt": 1}})
            enabled_args = SimpleNamespace(**vars(args(config)), warn=None, fail=None, include=[], exclude=[], count_blank_lines=False, ignore_comment_lines=False)
            with patch("agent_code_guard.analysis.pipeline.analyze_files", wraps=analyze_files) as analyze:
                results = run_guards(scope, enabled_args)
                self.assertEqual(analyze.call_count, 1)
                self.assertEqual(results[-1].guard_id, "callableSize")


class CallableSizeRunnerTests(CodeGuardTestCase):
    def test_explicit_supported_file_outside_reporting_root_uses_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as root_temp, tempfile.TemporaryDirectory() as source_temp:
            root = Path(root_temp)
            source = Path(source_temp) / "external.py"
            source.write_text("def external():\n    return 1\n", encoding="utf-8")
            config = write_config(root, {"enabled": False}, guards={"callableSize": {"enabled": True, "reviewAt": 2}})

            result = self.run_guard(root, str(source), "--config", str(config), "--json")

            self.assertEqual(result.returncode, 0)
            finding = self.read_json(result)["guards"]["callableSize"]["findings"][0]
            self.assertEqual(finding["path"], source.resolve().as_posix())

    def test_review_exit_policy_ci_and_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.py"
            source.write_text("def sample():\n    return 1\n", encoding="utf-8")
            config = write_config(root, {"enabled": False}, guards={"callableSize": {"enabled": True, "reviewAt": 1}})
            normal = self.run_guard(root, str(source), "--config", str(config), "--json")
            ci = self.run_guard(root, str(source), "--config", str(config), "--json", "--ci")
            self.assertEqual((normal.returncode, ci.returncode), (1, 0))
            data = self.read_json(normal)
            self.assertEqual(data["requiredPolicies"], ["callableSize"])
            self.assertEqual(data["guards"]["callableSize"]["findings"][0], {
                "path": "sample.py", "callable": "sample.sample",
                "range": {"startLine": 1, "endLine": 2}, "measured": 2,
                "state": "review", "thresholds": {"reviewAt": 1},
                "embeddedLanguage": "python",
            })

    def test_pass_has_no_policy_and_disabled_malformed_source_remains_loc_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "broken.py"
            source.write_text("def broken(:\n    pass\n", encoding="utf-8")
            config = write_config(root, {"enabled": True, "warnAt": 10, "failAt": 20}, guards={"callableSize": {"enabled": False}})
            result = self.run_guard(root, str(source), "--config", str(config), "--json")
            self.assertEqual((result.returncode, self.read_json(result)["requiredPolicies"]), (0, []))

    def test_enabled_pass_has_no_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.py"
            source.write_text("def sample():\n    return 1\n", encoding="utf-8")
            config = write_config(root, {"enabled": False}, guards={"callableSize": {"enabled": True, "reviewAt": 2}})
            result = self.run_guard(root, str(source), "--config", str(config), "--json")
            data = self.read_json(result)
            self.assertEqual((result.returncode, data["requiredPolicies"], data["guards"]["callableSize"]["state"]), (0, [], "pass"))

    def test_enabled_malformed_source_is_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "broken.py"
            source.write_text("def broken(:\n    pass\n", encoding="utf-8")
            config = write_config(root, {"enabled": False}, guards={"callableSize": {"enabled": True, "reviewAt": 80}})
            result = self.run_guard(root, str(source), "--config", str(config), "--json")
            self.assertEqual(result.returncode, 3)
            self.assertIn("syntax tree contains errors", self.read_json(result)["error"])


if __name__ == "__main__":
    unittest.main()
