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


if __name__ == "__main__":
    unittest.main()
