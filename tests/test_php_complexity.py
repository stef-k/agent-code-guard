from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import CodeGuardTestCase, write_config

from agent_code_guard.analysis import SyntaxAnalysisError, analyze_files
from agent_code_guard.guards import complexity, nesting


def write_php(root: Path, source: str, name: str = "sample.php") -> Path:
    path = root / name
    path.write_text(source, encoding="utf-8")
    return path


def callable_decisions(facts, identity: str):
    callable_fact = next(item for item in facts.callables if item.identity == identity)
    return callable_fact, [item for item in facts.decisions if item.callable_key == callable_fact.key]


def measurements(root: Path, path: Path, identity: str) -> tuple[int, int]:
    facts = analyze_files([path])
    complexity_result = complexity.run(root, complexity.Config(True, 99), facts)
    nesting_result = nesting.run(root, nesting.Config(True, 99), facts)
    complexities = {item.callable: item.measured for item in complexity_result.findings}
    nestings = {item.callable: item.measured for item in nesting_result.findings}
    return complexities[identity], nestings[identity]


class PhpFactNormalizationTests(unittest.TestCase):
    def test_if_elseif_chains_emit_one_condition_per_authored_condition_without_stacking_nesting(self) -> None:
        cases = {
            "simple": ("if ($x) { return 1; }", 2, 1, ["if_statement"]),
            "one_else_if": (
                "if ($x === 1) { return 1; } elseif ($x === 2) { return 2; } else { return 0; }",
                3, 1, ["if_statement", "else_if_clause"],
            ),
            "two_else_if": (
                "if ($x === 1) { return 1; } elseif ($x === 2) { return 2; } "
                "elseif ($x === 3) { return 3; } else { return 0; }",
                4, 1, ["if_statement", "else_if_clause", "else_if_clause"],
            ),
            "nested_in_else_if": (
                "if ($x === 1) { return 1; } elseif ($x === 2) { if ($x > 0) { return 2; } }",
                4, 2, ["if_statement", "else_if_clause", "if_statement"],
            ),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, (body, expected_complexity, expected_nesting, provider_kinds) in cases.items():
                with self.subTest(name=name):
                    path = write_php(root, f"<?php\nfunction {name}($x) {{ {body} }}\n", f"{name}.php")
                    facts = analyze_files([path])
                    callable_fact, decisions = callable_decisions(facts, f"{name}.{name}")
                    conditions = [item for item in decisions if item.category == "condition"]
                    self.assertEqual([item.provider_kind for item in conditions], provider_kinds)
                    self.assertTrue(all(item.callable_key == callable_fact.key for item in conditions))
                    self.assertEqual([item.source_range.start_line for item in conditions], sorted(item.source_range.start_line for item in conditions))
                    source = path.read_bytes()
                    for condition in (item for item in conditions if item.provider_kind == "else_if_clause"):
                        authored = source[condition.source_range.start.byte_offset:condition.source_range.end.byte_offset]
                        self.assertTrue(authored.startswith(b"elseif"))
                    self.assertEqual(measurements(root, path, callable_fact.identity), (expected_complexity, expected_nesting))

    def test_classic_switch_emits_one_fact_per_executable_non_default_destination(self) -> None:
        cases = {
            "distinct": ("case 1: a(); break; case 2: b(); break; default: c();", 2),
            "grouped": ("case 1: case 2: a(); break; default: b();", 1),
            "three_grouped": ("case 1: case 2: case 3: a(); break;", 1),
            "default_only": ("default: return 0;", 0),
            "case_with_default": ("case 1: default: return 0;", 1),
            "executable_fallthrough": ("case 1: prepare(); case 2: finish(); break;", 2),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, (arms, expected_count) in cases.items():
                with self.subTest(name=name):
                    path = write_php(root, f"<?php\nfunction {name}($x) {{ switch ($x) {{ {arms} }} }}\n", f"{name}.php")
                    facts = analyze_files([path])
                    callable_fact, decisions = callable_decisions(facts, f"{name}.{name}")
                    switch_arms = [item for item in decisions if item.category == "switch_arm"]
                    self.assertEqual(len(switch_arms), expected_count)
                    self.assertTrue(all(item.provider_kind == "case_statement" for item in switch_arms))
                    self.assertTrue(all(item.callable_key == callable_fact.key for item in switch_arms))
                    self.assertEqual(switch_arms, sorted(switch_arms, key=lambda item: item.source_range.start.byte_offset))
                    source = path.read_bytes()
                    self.assertTrue(all(source[item.source_range.start.byte_offset:item.source_range.end.byte_offset].startswith(b"case")
                                        for item in switch_arms))
                    self.assertEqual(measurements(root, path, callable_fact.identity), (1 + expected_count, 1))

    def test_switch_composes_with_existing_controls_without_case_nesting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_php(root, """<?php
function composed($x, $items) {
    if ($x) {
        foreach ($items as $item) {
            switch ($item) {
                case 1:
                    if ($x > 0) { work(); }
                    break;
                default:
                    break;
            }
        }
    }
}
""")
            self.assertEqual(measurements(root, path, "sample.composed"), (5, 4))

    def test_closure_owns_fixed_decisions_and_parent_does_not_inherit_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_php(root, """<?php
function owner() {
    $callback = function ($x) {
        if ($x === 1) {} elseif ($x === 2) {}
        switch ($x) { case 1: return 1; default: return 0; }
    };
}
""")
            facts = analyze_files([path])
            owner, owner_decisions = callable_decisions(facts, "sample.owner")
            callback = next(item for item in facts.callables if item.parent_callable == owner.identity)
            callback_decisions = [item for item in facts.decisions if item.callable_key == callback.key]
            self.assertEqual(owner_decisions, [])
            self.assertEqual([item.category for item in callback_decisions], ["condition", "condition", "switch_arm"])
            self.assertEqual(callback.parent_key, owner.key)
            self.assertEqual(measurements(root, path, callback.identity), (4, 1))

    def test_mixed_php_html_preserves_coordinates_identities_and_normalized_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_php(root, """<html>
<body>
text
<?php
function first($x) {
    if ($x === 1) { return 1; } elseif ($x === 2) { return 2; }
}
?>
more inert html
<?php
function second($x) {
    switch ($x) { case 1: return 1; case 2: case 3: return 2; default: return 0; }
}
?>
""", "Mixed.php")
            facts = analyze_files([path])
            self.assertEqual(facts.files[0].region_count, 1)
            by_identity = {item.identity: item for item in facts.callables}
            self.assertEqual(set(by_identity), {"Mixed.first", "Mixed.second"})
            self.assertEqual([by_identity[name].source_range.start_line for name in ("Mixed.first", "Mixed.second")], [5, 11])
            self.assertEqual([item.category for item in callable_decisions(facts, "Mixed.first")[1]], ["condition", "condition"])
            self.assertEqual([item.category for item in callable_decisions(facts, "Mixed.second")[1]], ["switch_arm", "switch_arm"])
            self.assertTrue(all(item.path == path and item.embedded_language == "php" for item in facts.callables))
            self.assertFalse(any(item.provider_kind in {"text", "text_interpolation"} for item in (*facts.controls, *facts.decisions)))

    def test_match_regression_ownership_default_exclusion_and_repeat_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_php(root, """<?php
function owner() {
    $callback = fn ($x) => match ($x) { 1 => 'one', 2, 3 => 'many', default => 'other' };
}
""")
            first = analyze_files([path])
            self.assertEqual(first, analyze_files([path]))
            owner = next(item for item in first.callables if item.identity == "sample.owner")
            callback = next(item for item in first.callables if item.parent_callable == owner.identity)
            self.assertEqual([item for item in first.decisions if item.callable_key == owner.key], [])
            arms = [item for item in first.decisions if item.callable_key == callback.key and item.category == "switch_arm"]
            self.assertEqual(len(arms), 2)

    def test_malformed_php_produces_no_partial_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_php(Path(temp), "<?php function broken( { switch ($x) { case 1: ?>")
            with self.assertRaises(SyntaxAnalysisError):
                analyze_files([path])


class PhpPublicComplexityTests(CodeGuardTestCase):
    def test_exact_audit_regressions_report_public_measurements_and_breakdowns(self) -> None:
        sources = {
            "elseif_focus.php": (
                "<?php function elseif_focus($x) { if ($x === 1) { return 1; } "
                "elseif ($x === 2) { return 2; } else { return 0; } }",
                3, {"condition": 2}, "elseif_focus.elseif_focus",
            ),
            "switch_focus.php": (
                "<?php function switch_focus($x) { switch ($x) { case 1: return 1; "
                "case 2: case 3: return 2; default: return 0; } }",
                3, {"switch_arm": 2}, "switch_focus.switch_focus",
            ),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = write_config(root, {"enabled": False}, guards={
                "callableSize": {"enabled": False},
                "nesting": {"enabled": False},
                "cyclomaticComplexity": {"reviewAt": 2},
                "markdownDocumentSize": {"enabled": False},
                "markdownSectionSize": {"enabled": False},
            })
            for name, (source, measured, decisions, identity) in sources.items():
                with self.subTest(name=name):
                    path = write_php(root, source, name)
                    result = self.run_guard(root, str(path), "--config", str(config), "--json")
                    payload = self.read_json(result)
                    finding = payload["guards"]["complexity"]["findings"][0]
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual((finding["callable"], finding["measured"], finding["state"]), (identity, measured, "review"))
                    self.assertEqual(finding["details"]["decisions"], decisions)
                    self.assertEqual(payload["requiredPolicies"], ["complexity"])

    def test_malformed_php_is_public_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_php(root, "<?php function broken( { elseif ($x) {}")
            result = self.run_guard(root, str(path), "--json")
            self.assertEqual(result.returncode, 3)
            payload = self.read_json(result)
            self.assertEqual(set(payload), {"error"})
            self.assertIn("syntax tree contains errors", payload["error"])


if __name__ == "__main__":
    unittest.main()
