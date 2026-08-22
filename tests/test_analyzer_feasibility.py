from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))

from research.analyzers.tree_sitter_analyzer import analyze_file  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "skills" / "code-guard" / "scripts"))

from result_model import CallableFinding, GuardResult  # noqa: E402


FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analyzers"

EXPECTED = {
    "python/callables.py": [
        ("callables.simple", 1, 2, 2, 0, 1),
        ("callables.long_linear", 5, 12, 8, 0, 1),
        ("callables.documented", 15, 22, 8, 0, 1),
        ("callables.outer", 25, 28, 4, 0, 1),
        ("callables.outer.local", 26, 27, 2, 0, 1),
        ("callables.Worker.method", 32, 33, 2, 0, 1),
    ],
    "python/decisions.py": [
        ("decisions.deeply_nested", 1, 8, 8, 4, 5),
        ("decisions.branching", 11, 20, 10, 1, 5),
        ("decisions.expressions", 23, 26, 4, 0, 4),
        ("decisions.patterns", 29, 39, 11, 2, 4),
    ],
    "go/callables.go": [
        ("sample.Simple", 3, 5, 3, 0, 1),
        ("sample.LongLinear", 7, 15, 9, 0, 1),
        ("sample.Documented", 17, 24, 8, 0, 1),
        ("sample.Worker.Method", 28, 30, 3, 0, 1),
    ],
    "go/decisions.go": [
        ("sample.DeeplyNested", 3, 15, 13, 4, 5),
        ("sample.Branching", 17, 24, 8, 1, 5),
        ("sample.Expressions", 26, 28, 3, 0, 3),
        ("sample.Switches", 30, 39, 10, 1, 3),
        ("sample.ElseIf", 41, 48, 8, 1, 3),
        ("sample.ValueSwitch", 50, 59, 10, 1, 3),
    ],
    "kotlin/callables.kt": [
        ("sample.simple", 3, 3, 1, 0, 1),
        ("sample.longLinear", 5, 13, 9, 0, 1),
        ("sample.documented", 15, 23, 9, 0, 1),
        ("sample.Worker.method", 26, 26, 1, 0, 1),
        ("sample.Worker.Worker", 28, 30, 3, 0, 1),
    ],
    "kotlin/decisions.kt": [
        ("sample.deeplyNested", 3, 16, 14, 4, 5),
        ("sample.branching", 18, 25, 8, 1, 5),
        ("sample.expressions", 27, 33, 7, 0, 4),
        ("sample.choices", 35, 39, 5, 1, 3),
        ("sample.localOwner", 41, 44, 4, 0, 1),
        ("sample.localOwner.local", 42, 42, 1, 0, 1),
        ("sample.elseIf", 46, 54, 9, 1, 3),
        ("sample.exceptions", 56, 64, 9, 2, 4),
    ],
    "csharp/Callables.cs": [
        ("Sample.Callables.Simple", 5, 5, 1, 0, 1),
        ("Sample.Callables.LongLinear", 7, 16, 10, 0, 1),
        ("Sample.Callables.Documented", 18, 26, 9, 0, 1),
        ("Sample.Callables.LocalOwner", 28, 32, 5, 0, 1),
        ("Sample.Callables.LocalOwner.Local", 30, 30, 1, 0, 1),
        ("Sample.Worker.Worker", 37, 37, 1, 0, 1),
    ],
    "csharp/Decisions.cs": [
        ("Sample.Decisions.DeeplyNested", 5, 23, 19, 4, 5),
        ("Sample.Decisions.Branching", 25, 33, 9, 1, 5),
        ("Sample.Decisions.Expressions", 35, 36, 2, 0, 4),
        ("Sample.Decisions.Choices", 38, 43, 6, 0, 3),
        ("Sample.Decisions.ElseIf", 45, 50, 6, 1, 3),
        ("Sample.Decisions.ClassicSwitch", 52, 61, 10, 1, 3),
        ("Sample.Decisions.Exceptions", 63, 72, 10, 2, 4),
        ("Sample.Decisions.WildcardSwitch", 74, 81, 8, 1, 2),
    ],
    "java/Callables.java": [
        ("sample.Callables.simple", 4, 6, 3, 0, 1),
        ("sample.Callables.longLinear", 8, 16, 9, 0, 1),
        ("sample.Callables.Callables", 18, 26, 9, 0, 1),
        ("sample.Callables.lambdaOwner", 28, 34, 7, 0, 1),
    ],
    "java/Decisions.java": [
        ("sample.Decisions.deeplyNested", 4, 17, 14, 4, 5),
        ("sample.Decisions.branching", 19, 26, 8, 1, 5),
        ("sample.Decisions.elseIf", 28, 32, 5, 1, 3),
        ("sample.Decisions.expressions", 34, 36, 3, 0, 4),
        ("sample.Decisions.exceptions", 38, 47, 10, 2, 4),
        ("sample.Decisions.statementSwitch", 49, 56, 8, 1, 3),
        ("sample.Decisions.expressionSwitch", 58, 64, 7, 1, 3),
    ],
    "javascript/callables.js": [
        ("callables.simple", 1, 3, 3, 0, 1),
        ("callables.longLinear", 5, 13, 9, 0, 1),
        ("callables.arrow", 15, 20, 6, 0, 1),
        ("callables.expression", 22, 24, 3, 0, 1),
        ("callables.helpers.method", 27, 29, 3, 0, 1),
        ("callables.Worker.constructor", 33, 35, 3, 0, 1),
        ("callables.Worker.method", 37, 39, 3, 0, 1),
        ("callables.localOwner", 42, 48, 7, 0, 1),
        ("callables.localOwner.local", 43, 43, 1, 0, 1),
        ("callables.localOwner.localExpression", 44, 46, 3, 0, 1),
    ],
    "javascript/decisions.js": [
        ("decisions.deeplyNested", 1, 14, 14, 4, 5),
        ("decisions.branching", 16, 23, 8, 1, 5),
        ("decisions.elseIf", 25, 29, 5, 1, 3),
        ("decisions.expressions", 31, 34, 4, 0, 4),
        ("decisions.choices", 36, 43, 8, 1, 3),
        ("decisions.callbackOwner", 45, 52, 8, 0, 1),
        ("decisions.callbackOwner.<callback@46:30>", 46, 49, 4, 1, 2),
        ("decisions.callbackOwner.<callback@50:18>", 50, 50, 1, 0, 2),
        ("decisions.exceptions", 54, 61, 8, 2, 3),
    ],
    "typescript/callables.ts": [
        ("callables.generic", 7, 12, 6, 0, 2),
        ("callables.arrow", 14, 16, 3, 0, 1),
        ("callables.expression", 18, 20, 3, 0, 1),
        ("callables.Worker.constructor", 23, 23, 1, 0, 1),
        ("callables.Worker.method", 25, 28, 4, 0, 2),
    ],
    "typescript/decisions.ts": [
        ("decisions.typedDecisions", 1, 7, 7, 1, 3),
        ("decisions.callbackOwner", 9, 16, 8, 0, 1),
        ("decisions.callbackOwner.<callback@10:31>", 10, 13, 4, 1, 2),
        ("decisions.callbackOwner.<callback@14:18>", 14, 14, 1, 0, 2),
    ],
    "jsx/components.jsx": [
        ("components.Card", 1, 13, 13, 0, 3),
        ("components.Card.<callback@8:32>", 8, 8, 1, 0, 2),
    ],
    "tsx/components.tsx": [
        ("components.UserCard", 6, 17, 12, 0, 2),
        ("components.UserCard.click", 7, 7, 1, 0, 2),
        ("components.UserCard.<callback@9:23>", 9, 9, 1, 0, 2),
        ("components.UserCard.<callback@11:30>", 11, 14, 4, 1, 2),
    ],
    "vue/Options.vue": [
        ("Options.calculate", 8, 13, 6, 1, 2),
    ],
    "vue/Setup.vue": [
        ("Setup.calculate", 8, 13, 6, 1, 2),
        ("Setup.normalize", 17, 19, 3, 0, 2),
    ],
}


def compact(measurement: object) -> tuple[object, ...]:
    return (
        measurement.identity,
        measurement.range.start_line,
        measurement.range.end_line,
        measurement.physical_loc,
        measurement.nesting_depth,
        measurement.cyclomatic_complexity,
    )


class FixtureMeasurementTests(unittest.TestCase):
    def test_all_fixture_measurements_match_the_explicit_contract(self) -> None:
        for relative, expected in EXPECTED.items():
            with self.subTest(fixture=relative):
                actual = [compact(value) for value in analyze_file(FIXTURES / relative)]
                self.assertEqual(actual, expected)

    def test_size_nesting_and_complexity_are_independent(self) -> None:
        for language, names in {
            "python": ("long_linear", "deeply_nested", "branching"),
            "go": ("LongLinear", "DeeplyNested", "Branching"),
            "kotlin": ("longLinear", "deeplyNested", "branching"),
            "csharp": ("LongLinear", "DeeplyNested", "Branching"),
        }.items():
            paths = (path for path in (FIXTURES / language).iterdir() if path.is_file())
            values = [value for path in paths for value in analyze_file(path)]
            by_name = {value.identity.rsplit(".", 1)[-1]: value for value in values}
            linear, deep, branching = (by_name[name] for name in names)
            with self.subTest(language=language):
                self.assertEqual((linear.nesting_depth, linear.cyclomatic_complexity), (0, 1))
                self.assertGreater(deep.nesting_depth, branching.nesting_depth)
                self.assertEqual(deep.cyclomatic_complexity, branching.cyclomatic_complexity)

    def test_repeated_analysis_is_deterministic(self) -> None:
        path = FIXTURES / "kotlin" / "decisions.kt"
        self.assertEqual(analyze_file(path), analyze_file(path))

    def test_syntax_errors_are_rejected_instead_of_partially_measured(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "broken.py"
            path.write_text("def broken(:\n    pass\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "syntax tree contains errors"):
                analyze_file(path)

    def test_python_native_ast_confirms_ranges_and_decorator_adjustment(self) -> None:
        path = FIXTURES / "python" / "callables.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        documented = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "documented")
        self.assertEqual((documented.lineno, documented.end_lineno), (16, 22))
        self.assertEqual(documented.decorator_list[0].lineno, 15)

    def test_typescript_bodyless_declarations_are_not_callables(self) -> None:
        measurements = analyze_file(FIXTURES / "typescript" / "callables.ts")
        self.assertNotIn("calculate", {value.identity.rsplit(".", 1)[-1] for value in measurements})
        self.assertEqual(len(measurements), 5)

    def test_jsx_markup_depth_does_not_increase_control_nesting(self) -> None:
        card = analyze_file(FIXTURES / "jsx" / "components.jsx")[0]
        self.assertEqual((card.nesting_depth, card.cyclomatic_complexity), (0, 3))

    def test_vue_regions_preserve_original_path_ranges_and_embedded_language(self) -> None:
        options = analyze_file(FIXTURES / "vue" / "Options.vue")
        setup = analyze_file(FIXTURES / "vue" / "Setup.vue")
        self.assertEqual((Path(options[0].path).name, options[0].language, options[0].range), (
            "Options.vue", "javascript", type(options[0].range)(8, 13),
        ))
        self.assertEqual([(value.language, value.range.start_line, value.range.end_line) for value in setup], [
            ("typescript", 8, 13), ("typescript", 17, 19),
        ])

    def test_vue_byte_mapping_handles_unicode_and_same_line_script_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Inline.vue"
            path.write_text("<template>é</template>\n<script>const inline = () => 1;</script>\n", encoding="utf-8")
            measurement = analyze_file(path)[0]
            self.assertEqual((measurement.identity, measurement.language), ("Inline.inline", "javascript"))
            self.assertEqual((measurement.range.start_line, measurement.range.end_line), (2, 2))


class CallableResultCompatibilityTests(unittest.TestCase):
    def test_callable_finding_is_additive_and_json_serializable(self) -> None:
        finding = CallableFinding(
            path="src/Foo.kt", callable="Foo.process", start_line=20, end_line=48,
            measured=5, state="review", thresholds={"reviewAt": 4}, details={"conditional": 3, "loop": 2},
        )
        result = GuardResult("nesting", "review", [finding])
        payload = {"requiredPolicies": result.required_policies, "guards": {"nesting": result.to_json()}}
        encoded = json.loads(json.dumps(payload))
        self.assertEqual(encoded["requiredPolicies"], ["nesting"])
        self.assertEqual(encoded["guards"]["nesting"]["findings"][0], {
            "path": "src/Foo.kt", "callable": "Foo.process",
            "range": {"startLine": 20, "endLine": 48}, "measured": 5,
            "state": "review", "thresholds": {"reviewAt": 4}, "details": {"conditional": 3, "loop": 2},
        })

    def test_vue_finding_keeps_container_path_range_and_embedded_language(self) -> None:
        finding = CallableFinding(
            path="src/Foo.vue", callable="Foo.calculate", start_line=21, end_line=35,
            measured=4, state="review", embedded_language="typescript",
        )
        value = finding.to_json()
        self.assertEqual(value["path"], "src/Foo.vue")
        self.assertEqual(value["range"], {"startLine": 21, "endLine": 35})
        self.assertEqual(value["embeddedLanguage"], "typescript")


if __name__ == "__main__":
    unittest.main()
