from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent_code_guard.analysis.facts import AnalysisFacts, CallableFact, CallableKey, DecisionFact, FileFacts, SourcePoint, SourceRange
from agent_code_guard.analysis import analyze_files
from agent_code_guard.code_guard import payload, print_text
from agent_code_guard.guards import complexity
from agent_code_guard.result_model import GuardResult


def args(config: Path | None = None) -> SimpleNamespace:
    return SimpleNamespace(config=str(config) if config else None)


def source_range(start: int, end: int) -> SourceRange:
    return SourceRange(SourcePoint(start, 1, start * 10), SourcePoint(end + 1, 1, (end + 1) * 10))


def facts(categories: list[str], *, language: str = "python", boundary: str = "declaration") -> AnalysisFacts:
    path = Path("src/example.py")
    value_range = source_range(10, 80)
    key = CallableKey(path, language, "module.run", value_range)
    callable_fact = CallableFact(path, language, "module.run", value_range, None, boundary, key, None)
    decisions = tuple(DecisionFact("module.run", key, category, category, source_range(20 + index, 20 + index)) for index, category in enumerate(categories))
    return AnalysisFacts((FileFacts(path, (callable_fact,), (), decisions, 1),))


class ComplexityConfigTests(unittest.TestCase):
    def write(self, root: Path, value: object, *, whole_document: bool = False) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        path = root / "config.json"
        document = value if whole_document else {"guards": {"cyclomaticComplexity": value}}
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_default_override_and_disable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = [
                ({}, (True, 15)),
                ({"guards": {}}, (True, 15)),
                ({"guards": {"cyclomaticComplexity": {}}}, (True, 15)),
                ({"guards": {"cyclomaticComplexity": {"enabled": True}}}, (True, 15)),
                ({"guards": {"cyclomaticComplexity": {"reviewAt": 20}}}, (True, 20)),
                ({"guards": {"cyclomaticComplexity": {"enabled": True, "reviewAt": 20}}}, (True, 20)),
                ({"guards": {"cyclomaticComplexity": {"enabled": False}}}, (False, None)),
                ({"guards": {"cyclomaticComplexity": {"enabled": False, "reviewAt": "ignored"}}}, (False, None)),
            ]
            for index, (document, expected) in enumerate(cases):
                config = complexity.load_config(args(self.write(root / f"case-{index}", document, whole_document=True)))
                self.assertEqual((config.enabled, config.review_at), expected)

    def test_enabled_and_review_at_are_strict_json_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.mkdir(exist_ok=True)
            for value in [None, 1, 0, "true", [], {}]:
                with self.subTest(enabled=value), self.assertRaisesRegex(ValueError, "enabled must be a boolean"):
                    complexity.load_config(args(self.write(root, {"enabled": value})))
            for value in [None, True, False, 1.5, "15", 0, -1]:
                with self.subTest(reviewAt=value), self.assertRaisesRegex(ValueError, "reviewAt must be a positive integer"):
                    complexity.load_config(args(self.write(root, {"reviewAt": value})))


class ComplexityEvaluationTests(unittest.TestCase):
    fixtures = Path(__file__).parent / "fixtures" / "analyzers"

    def test_baseline_exact_threshold_next_and_never_fail(self) -> None:
        for count, expected in [(0, (1, "pass")), (14, (15, "pass")), (15, (16, "review"))]:
            with self.subTest(count=count):
                result = complexity.run(Path.cwd(), complexity.Config(True, 15), facts(["condition"] * count))
                self.assertEqual((result.findings[0].measured, result.findings[0].state), expected)
                self.assertNotEqual(result.state, "fail")

    def test_breakdown_is_non_zero_sorted_and_json_shape_is_explanatory(self) -> None:
        result = complexity.run(Path.cwd(), complexity.Config(True, 3), facts(["ternary", "condition", "loop", "condition"]))
        finding = result.findings[0]
        self.assertEqual(finding.details, {"boundaryKind": "declaration", "decisions": {"condition": 2, "loop": 1, "ternary": 1}})
        self.assertEqual(finding.to_json(), {
            "path": "src/example.py",
            "callable": "module.run",
            "range": {"startLine": 10, "endLine": 80},
            "measured": 5,
            "state": "review",
            "thresholds": {"reviewAt": 3},
            "details": {"boundaryKind": "declaration", "decisions": {"condition": 2, "loop": 1, "ternary": 1}},
            "embeddedLanguage": "python",
        })
        self.assertEqual(result.required_policies, ["complexity"])

    def test_callable_key_ownership_resets_child_baseline(self) -> None:
        path = Path("owner.cs")
        outer_range, child_range = source_range(1, 20), source_range(5, 10)
        outer_key = CallableKey(path, "c_sharp", "Owner", outer_range)
        child_key = CallableKey(path, "c_sharp", "Owner.<callback@5>", child_range)
        callables = (
            CallableFact(path, "c_sharp", "Owner", outer_range, None, "declaration", outer_key, None),
            CallableFact(path, "c_sharp", "Owner.<callback@5>", child_range, "Owner", "lambda", child_key, outer_key),
        )
        decisions = (
            DecisionFact("Owner", outer_key, "condition", "if_statement", source_range(2, 2)),
            DecisionFact("Owner.<callback@5>", child_key, "loop", "while_statement", source_range(7, 7)),
            DecisionFact("Owner.<callback@5>", child_key, "condition", "if_statement", source_range(8, 8)),
        )
        analysis = AnalysisFacts((FileFacts(path, callables, (), decisions, 1),))
        by_name = {item.callable: item for item in complexity.run(Path.cwd(), complexity.Config(True, 99), analysis).findings}
        self.assertEqual((by_name["Owner"].measured, by_name["Owner.<callback@5>"].measured), (2, 3))

    def test_language_neutral_over_representative_production_facts(self) -> None:
        cases = {
            "python/decisions.py": ("decisions.deeply_nested", 5),
            "csharp/Decisions.cs": ("Sample.Decisions.DeeplyNested", 5),
            "javascript/decisions.js": ("decisions.deeplyNested", 5),
            "kotlin/decisions.kt": ("sample.deeplyNested", 5),
            "go/decisions.go": ("sample.DeeplyNested", 5),
            "rust/second_wave.rs": ("second_wave.evaluate", 8),
        }
        for relative, (identity, expected) in cases.items():
            with self.subTest(relative=relative):
                analysis = analyze_files([self.fixtures / relative])
                result = complexity.run(self.fixtures, complexity.Config(True, 99), analysis)
                self.assertEqual({item.callable: item.measured for item in result.findings}[identity], expected)

    def test_short_circuit_and_fallback_syntax_add_no_boolean_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = {
                "sample.py": "def sample(a, b, c):\n    if a and b and c:\n        return a or b\n",
                "sample.js": "function sample(a, b, c) { if (a && b || c) return a || b; }\n",
            }
            for name, source in sources.items():
                path = root / name
                path.write_text(source, encoding="utf-8")
                result = complexity.run(root, complexity.Config(True, 99), analyze_files([path]))
                self.assertEqual(result.findings[0].measured, 2)

    def test_vue_preserves_original_coordinates_and_embedded_language(self) -> None:
        result = complexity.run(self.fixtures, complexity.Config(True, 99), analyze_files([self.fixtures / "vue/Setup.vue"]))
        finding = {item.callable: item for item in result.findings}["Setup.calculate"]
        self.assertEqual((finding.path, finding.start_line, finding.embedded_language), ("vue/Setup.vue", 8, "typescript"))

    def test_human_prints_only_review(self) -> None:
        reviewed = complexity.run(Path.cwd(), complexity.Config(True, 1), facts(["condition"]))
        passed = complexity.run(Path.cwd(), complexity.Config(True, 15), facts([]))
        stream = io.StringIO()
        with redirect_stdout(stream):
            print_text(payload([GuardResult("loc", "pass", []), reviewed]))
        self.assertIn("complexity 2 (review 1)", stream.getvalue())
        stream = io.StringIO()
        with redirect_stdout(stream):
            print_text(payload([GuardResult("loc", "pass", []), passed]))
        self.assertNotIn("module.run", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
