from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import CodeGuardTestCase, analyze_source_paths as analyze_files, analyze_source_paths_for_runner, write_config
from agent_code_guard.analysis.pipeline import analyze_files_for_runner as production_analyze_files_for_runner

analyze_files_for_runner = analyze_source_paths_for_runner
from agent_code_guard.code_guard import run_guards
from agent_code_guard.file_selection import ResolvedScope
from agent_code_guard.guards import nesting


def args(config: Path | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        config=str(config) if config else None,
        warn=None,
        fail=None,
        include=[],
        exclude=[],
        count_blank_lines=False,
        ignore_comment_lines=False,
    )


class NestingConfigTests(unittest.TestCase):
    def write_document(self, root: Path, value: object) -> Path:
        path = root / "config.json"
        path.write_text(json.dumps({"guards": {"nesting": value}}), encoding="utf-8")
        return path

    def test_omitted_empty_override_and_disable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = [
                ({}, (True, 4)),
                ({"guards": {}}, (True, 4)),
                ({"guards": {"nesting": {}}}, (True, 4)),
                ({"guards": {"nesting": {"enabled": True}}}, (True, 4)),
                ({"guards": {"nesting": {"reviewAt": 6}}}, (True, 6)),
                ({"guards": {"nesting": {"enabled": True, "reviewAt": 8}}}, (True, 8)),
                ({"guards": {"nesting": {"enabled": False}}}, (False, None)),
                ({"guards": {"nesting": {"enabled": False, "reviewAt": "ignored"}}}, (False, None)),
            ]
            for index, (document, expected) in enumerate(cases):
                path = root / f"config-{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                config = nesting.load_config(args(path))
                self.assertEqual((config.enabled, config.review_at), expected)

    def test_no_discovered_config_uses_builtin_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            previous = Path.cwd()
            try:
                os.chdir(temp)
                config = nesting.load_config(args())
            finally:
                os.chdir(previous)
            self.assertEqual((config.enabled, config.review_at), (True, nesting.DEFAULT_REVIEW_AT))

    def test_present_enabled_must_be_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for value in [None, 1, 0, "true", [], {}]:
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "guards.nesting.enabled must be a boolean"):
                    nesting.load_config(args(self.write_document(root, {"enabled": value})))

    def test_explicit_review_at_requires_positive_json_integer_while_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for value in [None, True, False, 1.5, "4", 0, -1]:
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "guards.nesting.reviewAt must be a positive integer"):
                    nesting.load_config(args(self.write_document(root, {"reviewAt": value})))


class NestingEvaluationTests(unittest.TestCase):
    fixtures = Path(__file__).parent / "fixtures" / "analyzers"

    def findings(self, relative: str, review_at: int = 99):
        facts = analyze_files([self.fixtures / relative])
        result = nesting.run(self.fixtures, nesting.Config(True, review_at), facts)
        return result, {finding.callable: finding for finding in result.findings}

    def test_deep_is_greater_than_wide_and_exact_threshold_passes(self) -> None:
        result, by_name = self.findings("javascript/decisions.js", 4)
        self.assertEqual((by_name["decisions.deeplyNested"].measured, by_name["decisions.deeplyNested"].state), (4, "pass"))
        self.assertEqual(by_name["decisions.branching"].measured, 1)
        self.assertEqual(result.state, "pass")

        result, by_name = self.findings("javascript/decisions.js", 3)
        self.assertEqual((by_name["decisions.deeplyNested"].state, result.state), ("review", "review"))
        self.assertNotIn("fail", {finding.state for finding in result.findings})

    def test_builtin_threshold_4_passes_and_5_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exact = root / "exact.py"
            exact.write_text("def exact():\n    if True:\n        while True:\n            for x in []:\n                if x:\n                    return x\n", encoding="utf-8")
            over = root / "over.py"
            over.write_text("def over():\n    if True:\n        while True:\n            for x in []:\n                if x:\n                    try:\n                        return x\n                    except Exception:\n                        return None\n", encoding="utf-8")
            result = nesting.run(root, nesting.Config(True, nesting.DEFAULT_REVIEW_AT), analyze_files([exact, over]))
            by_name = {item.callable: item for item in result.findings}
            self.assertEqual((by_name["exact.exact"].measured, by_name["exact.exact"].state), (4, "pass"))
            self.assertEqual((by_name["over.over"].measured, by_name["over.over"].state), (5, "review"))
            self.assertNotIn("fail", {item.state for item in result.findings})

    def test_else_if_switch_and_try_families_use_normalized_fact_relationships(self) -> None:
        _, javascript = self.findings("javascript/decisions.js")
        self.assertEqual(javascript["decisions.elseIf"].measured, 1)
        self.assertEqual(javascript["decisions.choices"].measured, 1)
        self.assertEqual(javascript["decisions.exceptions"].measured, 2)

    def test_nested_callable_and_javascript_callback_reset_depth(self) -> None:
        _, javascript = self.findings("javascript/decisions.js")
        self.assertEqual(javascript["decisions.callbackOwner"].measured, 0)
        callback = next(value for name, value in javascript.items() if "<callback@" in name)
        self.assertEqual(callback.measured, 1)

    def test_mainstream_lambda_controls_reset_without_polluting_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "owner.cs"
            source.write_text(
                "class Sample { void Owner(int[] values) { if (values.Length > 0) {\n"
                "System.Action callback = () => { if (values.Length > 1) { while (true) { break; } } };\n"
                "} } }\n",
                encoding="utf-8",
            )
            facts = analyze_files([source])
            result = nesting.run(root, nesting.Config(True, 99), facts)
            by_name = {finding.callable: finding for finding in result.findings}
            callback = next(finding for name, finding in by_name.items() if "<callback@" in name)
            self.assertEqual((by_name["Sample.Owner"].measured, callback.measured), (1, 2))

    def test_jsx_markup_does_not_count(self) -> None:
        _, findings = self.findings("jsx/components.jsx")
        self.assertTrue(findings)
        self.assertEqual({finding.measured for finding in findings.values()}, {0})

    def test_vue_uses_script_controls_with_original_path_range_and_language(self) -> None:
        _, findings = self.findings("vue/Setup.vue")
        finding = findings["Setup.calculate"]
        self.assertEqual(
            (finding.path, finding.start_line, finding.measured, finding.embedded_language),
            ("vue/Setup.vue", 8, 1, "typescript"),
        )

    def test_second_wave_structural_semantics(self) -> None:
        cases = {
            "rust/second_wave.rs": ("second_wave.evaluate", 3),
            "swift/second_wave.swift": ("second_wave.evaluate", 2),
            "php/Mixed.php": ("Mixed.Worker.run", 2),
            "cpp/second_wave.cpp": ("second_wave.choose", 2),
            "dart/second_wave.dart": ("second_wave.evaluate", 3),
        }
        for relative, (identity, expected) in cases.items():
            with self.subTest(relative=relative):
                _, findings = self.findings(relative)
                self.assertEqual(findings[identity].measured, expected)

    def test_deepest_line_is_deterministic_optional_explanation(self) -> None:
        _, findings = self.findings("javascript/decisions.js")
        self.assertEqual(findings["decisions.deeplyNested"].details, {"deepestLine": 6})
        self.assertIsNone(findings["decisions.callbackOwner"].details)


class NestingOrchestrationTests(unittest.TestCase):
    def test_analysis_activation_matrix_builds_shared_facts_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.py"
            source.write_text("def sample():\n    if True:\n        return 1\n", encoding="utf-8")
            scope = ResolvedScope(root, (source,))
            configurations = [
                ({}, 1, ["loc", "callableSize", "nesting", "complexity", "markdownDocumentSize", "markdownSectionSize"]),
                ({"cyclomaticComplexity": {"enabled": False}}, 1, ["loc", "callableSize", "nesting", "markdownDocumentSize", "markdownSectionSize"]),
                ({"callableSize": {"enabled": False}, "nesting": {"enabled": False}}, 1, ["loc", "complexity", "markdownDocumentSize", "markdownSectionSize"]),
                ({"callableSize": {"enabled": False}, "nesting": {"enabled": False}, "cyclomaticComplexity": {"enabled": False}}, 0, ["loc", "markdownDocumentSize", "markdownSectionSize"]),
                ({
                    "callableSize": {"enabled": True, "reviewAt": 3},
                    "nesting": {"enabled": True, "reviewAt": 1},
                    "cyclomaticComplexity": {"enabled": True, "reviewAt": 2},
                }, 1, ["loc", "callableSize", "nesting", "complexity", "markdownDocumentSize", "markdownSectionSize"]),
            ]
            for guards, expected_calls, expected_ids in configurations:
                config = write_config(root, {"enabled": False}, guards=guards)
                with self.subTest(guards=guards), patch(
                    "agent_code_guard.analysis.pipeline.analyze_files_for_runner",
                wraps=production_analyze_files_for_runner,
                ) as analyze:
                    results = run_guards(scope, args(config))
                    self.assertEqual(analyze.call_count, expected_calls)
                    self.assertEqual([result.guard_id for result in results], expected_ids)

    def test_all_syntax_guards_disabled_do_not_import_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "broken.py"
            source.write_text("def broken(:\n    pass\n", encoding="utf-8")
            scope = ResolvedScope(root, (source,))
            config = write_config(root, {"enabled": True, "warnAt": 10, "failAt": 20}, guards={
                "callableSize": {"enabled": False}, "nesting": {"enabled": False}, "cyclomaticComplexity": {"enabled": False},
                "markdownDocumentSize": {"enabled": False}, "markdownSectionSize": {"enabled": False},
            })
            with patch("agent_code_guard.code_guard.import_module") as loader:
                results = run_guards(scope, args(config))
                loader.assert_not_called()
                self.assertEqual([result.guard_id for result in results], ["loc"])

class NestingRunnerTests(CodeGuardTestCase):
    def test_review_ci_json_shape_human_output_and_external_path(self) -> None:
        with tempfile.TemporaryDirectory() as root_temp, tempfile.TemporaryDirectory() as source_temp:
            root = Path(root_temp)
            source = Path(source_temp) / "external.py"
            source.write_text(
                "def external():\n    if True:\n        while True:\n            return 1\n",
                encoding="utf-8",
            )
            config = write_config(root, {"enabled": False}, guards={"nesting": {"enabled": True, "reviewAt": 1}})
            normal = self.run_guard(root, str(source), "--config", str(config), "--json")
            ci = self.run_guard(root, str(source), "--config", str(config), "--json", "--ci")
            human = self.run_guard(root, str(source), "--config", str(config))

            self.assertEqual((normal.returncode, ci.returncode, human.returncode), (1, 0, 1))
            data = self.read_json(normal)
            self.assertEqual(data["requiredPolicies"], ["nesting"])
            self.assertEqual(data["guards"]["nesting"]["findings"][0], {
                "path": source.resolve().as_posix(),
                "callable": "external.external",
                "range": {"startLine": 1, "endLine": 4},
                "measured": 2,
                "state": "review",
                "thresholds": {"reviewAt": 1},
                "details": {"deepestLine": 3},
                "embeddedLanguage": "python",
            })
            self.assertIn("nesting depth 2 (review 1; deepest at line 3)", human.stdout)

    def test_pass_routes_no_policy_and_combined_reviews_are_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.py"
            source.write_text(
                "def sample():\n    if True:\n        while True:\n            return 1\n",
                encoding="utf-8",
            )
            pass_config = write_config(root, {"enabled": False}, guards={"nesting": {"enabled": True, "reviewAt": 2}})
            passed = self.run_guard(root, str(source), "--config", str(pass_config), "--json")
            self.assertEqual((passed.returncode, self.read_json(passed)["requiredPolicies"]), (0, []))

            nesting_only_review = write_config(root, {"enabled": False}, guards={
                "callableSize": {"enabled": True, "reviewAt": 4},
                "nesting": {"enabled": True, "reviewAt": 1},
            })
            reviewed = self.run_guard(root, str(source), "--config", str(nesting_only_review), "--json")
            self.assertEqual(self.read_json(reviewed)["requiredPolicies"], ["nesting"])

            both_review = write_config(root, {"enabled": False}, guards={
                "callableSize": {"enabled": True, "reviewAt": 1},
                "nesting": {"enabled": True, "reviewAt": 1},
            })
            reviewed = self.run_guard(root, str(source), "--config", str(both_review), "--json")
            self.assertEqual(self.read_json(reviewed)["requiredPolicies"], ["callableSize", "nesting"])

    def test_loc_fail_dominates_nesting_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.py"
            source.write_text("def sample():\n    if True:\n        while True:\n            return 1\n", encoding="utf-8")
            config = root / "code-guard.config.json"
            config.write_text(json.dumps({"version": 1, "guards": {
                "loc": {"enabled": True, "warnAt": 1, "failAt": 2},
                "nesting": {"enabled": True, "reviewAt": 1},
            }}), encoding="utf-8")
            result = self.run_guard(root, str(source), "--config", str(config), "--json", "--ci")
            data = self.read_json(result)
            self.assertEqual((result.returncode, data["overall"]), (2, "fail"))
            self.assertEqual(data["requiredPolicies"], ["loc", "nesting"])

    def test_enabled_malformed_source_is_exit_three_but_disabled_is_loc_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "broken.py"
            source.write_text("def broken(:\n    pass\n", encoding="utf-8")
            enabled = write_config(root, {"enabled": False}, guards={"nesting": {"enabled": True, "reviewAt": 4}})
            result = self.run_guard(root, str(source), "--config", str(enabled), "--json")
            self.assert_syntax_unavailable(result, "broken.py")
            self.assertIn("syntax tree contains errors", self.read_json(result)["unavailable"][0]["message"])

            disabled = write_config(root, {"enabled": True, "warnAt": 10, "failAt": 20}, guards={
                "callableSize": {"enabled": False}, "nesting": {"enabled": False}, "cyclomaticComplexity": {"enabled": False},
                "markdownDocumentSize": {"enabled": False}, "markdownSectionSize": {"enabled": False},
            })
            result = self.run_guard(root, str(source), "--config", str(disabled), "--json")
            self.assertEqual((result.returncode, list(self.read_json(result)["guards"])), (0, ["loc"]))


if __name__ == "__main__":
    unittest.main()
