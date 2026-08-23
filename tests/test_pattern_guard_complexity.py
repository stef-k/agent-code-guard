from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import CodeGuardTestCase, write_config

from agent_code_guard.analysis import SyntaxAnalysisError, analyze_files


PYTHON_AUDIT = '''def classify(value):
    match value:
        case 1:
            return "one"
        case x if x > 1:
            return "many"
        case _:
            return "other"
'''

C_SHARP_AUDIT = '''class C
{
    int Classify(int x) =>
        x switch
        {
            1 when x > 0 => 1,
            _ => 0
        };
}
'''


def write_source(root: Path, name: str, source: str) -> Path:
    path = root / name
    path.write_text(source, encoding="utf-8")
    return path


def owned_decisions(facts, callable_fact):
    return [item for item in facts.decisions if item.callable_key == callable_fact.key]


class PatternGuardFactTests(unittest.TestCase):
    def test_exact_python_audit_emits_authored_arm_and_guard_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_source(Path(temp), "audit.py", PYTHON_AUDIT)
            facts = analyze_files([path])
            self.assertEqual(facts, analyze_files([path]))
            decisions = owned_decisions(facts, facts.callables[0])
            self.assertEqual([item.category for item in decisions],
                             ["switch_arm", "switch_arm", "pattern_guard"])
            self.assertEqual([item.provider_kind for item in decisions],
                             ["case_clause", "case_clause", "comparison_operator"])
            source = path.read_bytes()
            self.assertEqual([item.source_range.start.byte_offset for item in decisions],
                             [source.index(b"case 1"), source.index(b"case x"), source.index(b"x > 1")])
            guard = decisions[-1].source_range
            self.assertEqual(source[guard.start.byte_offset:guard.end.byte_offset], b"x > 1")

    def test_exact_csharp_audit_emits_authored_arm_and_guard_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_source(Path(temp), "audit.cs", C_SHARP_AUDIT)
            facts = analyze_files([path])
            self.assertEqual(facts, analyze_files([path]))
            decisions = owned_decisions(facts, facts.callables[0])
            self.assertEqual([item.category for item in decisions], ["switch_arm", "pattern_guard"])
            self.assertEqual([item.provider_kind for item in decisions],
                             ["switch_expression_arm", "binary_expression"])
            source = path.read_bytes()
            self.assertEqual([item.source_range.start.byte_offset for item in decisions],
                             [source.index(b"1 when"), source.index(b"x > 0")])
            guard = decisions[-1].source_range
            self.assertEqual(source[guard.start.byte_offset:guard.end.byte_offset], b"x > 0")

    def test_python_case_matrix_preserves_guarded_and_unguarded_wildcards(self) -> None:
        source = '''def classify(value, ready):
    match value:
        case 1:
            return 1
        case x if x > 1 and ready(x):
            return 2
        case y if y < 0:
            return 3
        case _ if ready(value):
            return 4
        case _:
            return 0
'''
        with tempfile.TemporaryDirectory() as temp:
            facts = analyze_files([write_source(Path(temp), "matrix.py", source)])
            decisions = owned_decisions(facts, facts.callables[0])
            self.assertEqual([item.category for item in decisions], [
                "switch_arm", "switch_arm", "pattern_guard", "switch_arm",
                "pattern_guard", "switch_arm", "pattern_guard",
            ])
            self.assertEqual(sum(item.category == "switch_arm" for item in decisions), 4)
            self.assertEqual(sum(item.category == "pattern_guard" for item in decisions), 3)
            self.assertFalse(any(item.category == "condition" for item in decisions))

    def test_python_guard_does_not_add_nesting_and_child_owns_decisions(self) -> None:
        source = '''def owner():
    def child(value):
        match value:
            case x if x > 0:
                if x > 10:
                    return x
            case _:
                return 0
'''
        with tempfile.TemporaryDirectory() as temp:
            facts = analyze_files([write_source(Path(temp), "ownership.py", source)])
            parent = next(item for item in facts.callables if item.parent_key is None)
            child = next(item for item in facts.callables if item.parent_key == parent.key)
            self.assertEqual(owned_decisions(facts, parent), [])
            self.assertEqual([item.category for item in owned_decisions(facts, child)],
                             ["switch_arm", "pattern_guard", "condition"])
            match = next(item for item in facts.controls if item.provider_kind == "match_statement")
            condition = next(item for item in facts.controls if item.provider_kind == "if_statement")
            self.assertEqual(condition.parent_control_range, match.source_range)

    def test_csharp_case_matrix_and_nested_switches_emit_one_guard_each(self) -> None:
        source = '''class C
{
    int F(int x, int y) => x switch
    {
        1 when x > 0 && Ready(x) => y switch
        {
            2 when y > 0 => 2,
            _ => 0
        },
        2 => 2,
        _ when x < 0 => -1,
        _ => 0
    };
    bool Ready(int x) => true;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = write_source(Path(temp), "nested.cs", source)
            facts = analyze_files([path])
            self.assertEqual(facts, analyze_files([path]))
            target = next(item for item in facts.callables if item.identity.endswith(".F"))
            decisions = owned_decisions(facts, target)
            self.assertEqual([item.category for item in decisions], [
                "switch_arm", "pattern_guard", "switch_arm", "pattern_guard",
                "switch_arm", "switch_arm", "pattern_guard",
            ])
            self.assertEqual(sum(item.category == "switch_arm" for item in decisions), 4)
            self.assertEqual(sum(item.category == "pattern_guard" for item in decisions), 3)
            self.assertTrue(all(item.provider_kind == "binary_expression"
                                for item in decisions if item.category == "pattern_guard"))
            self.assertFalse(any(item.category == "condition" for item in decisions))
            self.assertFalse(any(item.callable_key == target.key for item in facts.controls))
            starts = [item.source_range.start.byte_offset for item in decisions]
            self.assertEqual(starts, sorted(starts))
            authored = path.read_bytes()
            self.assertIn(authored.index(b"x > 0 && Ready(x)"), starts)
            self.assertIn(authored.index(b"y > 0"), starts)

    def test_csharp_lambda_and_local_function_own_their_guarded_arms(self) -> None:
        source = '''class C
{
    int Owner(int x)
    {
        System.Func<int, int> lambda = y => y switch { 1 when y > 0 => 1, _ => 0 };
        int Local(int y) => y switch { _ when y > 0 => 1, _ => 0 };
        return lambda(x) + Local(x);
    }
}
'''
        with tempfile.TemporaryDirectory() as temp:
            facts = analyze_files([write_source(Path(temp), "ownership.cs", source)])
            parent = next(item for item in facts.callables if item.identity.endswith(".Owner"))
            children = [item for item in facts.callables if item.parent_key == parent.key]
            self.assertEqual(len(children), 2)
            self.assertEqual(owned_decisions(facts, parent), [])
            for child in children:
                self.assertEqual([item.category for item in owned_decisions(facts, child)],
                                 ["switch_arm", "pattern_guard"])

    def test_rust_and_swift_pattern_guard_regressions(self) -> None:
        sources = {
            "guard.rs": (
                "fn choose(x: i32) -> i32 { match x { n if n > 0 => 1, _ => 0 } }",
                ["match_arm", "binary_expression"], b"n > 0",
            ),
            "guard.swift": ('''func choose(_ x: Int) -> Int {
    switch x {
    case let n where n > 0: return 1
    default: return 0
    }
}
''', ["switch_entry", "comparison_expression"], b"n > 0"),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, (source, provider_kinds, guard_text) in sources.items():
                with self.subTest(name=name):
                    path = write_source(root, name, source)
                    facts = analyze_files([path])
                    callable_fact = facts.callables[0]
                    decisions = owned_decisions(facts, callable_fact)
                    self.assertEqual([item.category for item in decisions],
                                     ["switch_arm", "pattern_guard"])
                    self.assertEqual([item.provider_kind for item in decisions], provider_kinds)
                    self.assertTrue(all(item.callable_key == callable_fact.key for item in decisions))
                    self.assertEqual(len({item.source_range.start.byte_offset for item in decisions}), 2)
                    guard = decisions[-1].source_range
                    authored = path.read_bytes()
                    self.assertEqual(authored[guard.start.byte_offset:guard.end.byte_offset], guard_text)
                    self.assertEqual(facts, analyze_files([root / name]))

    def test_malformed_python_and_csharp_fail_closed(self) -> None:
        sources = {"broken.py": "def broken(x):\n match x:\n  case x if:\n   pass\n",
                   "broken.cs": "class C { int F(int x) => x switch { 1 when => 1, _ => 0 }; }"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in sources.items():
                with self.subTest(name=name), self.assertRaises(SyntaxAnalysisError):
                    analyze_files([write_source(root, name, source)])


class PatternGuardPublicTests(CodeGuardTestCase):
    def config(self, root: Path, review_at: int) -> Path:
        return write_config(root, {"enabled": False}, guards={
            "callableSize": {"enabled": False},
            "nesting": {"enabled": False},
            "cyclomaticComplexity": {"reviewAt": review_at},
            "markdownDocumentSize": {"enabled": False},
            "markdownSectionSize": {"enabled": False},
        })

    def test_exact_audits_report_public_measurement_and_breakdown(self) -> None:
        cases = {
            "audit.py": (PYTHON_AUDIT, 4, {"pattern_guard": 1, "switch_arm": 2}),
            "audit.cs": (C_SHARP_AUDIT, 3, {"pattern_guard": 1, "switch_arm": 1}),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.config(root, 1)
            for name, (source, measured, decisions) in cases.items():
                with self.subTest(name=name):
                    path = write_source(root, name, source)
                    result = self.run_guard(root, str(path), "--config", str(config), "--json")
                    repeat = self.run_guard(root, str(path), "--config", str(config), "--json")
                    payload = self.read_json(result)
                    self.assertEqual(payload, self.read_json(repeat))
                    finding = payload["guards"]["complexity"]["findings"][0]
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(finding["state"], "review")
                    self.assertEqual((finding["measured"], finding["details"]["decisions"]),
                                     (measured, decisions))
                    self.assertEqual(payload["requiredPolicies"], ["complexity"])

    def test_exact_audits_pass_at_their_measurement_threshold(self) -> None:
        cases = {"audit.py": (PYTHON_AUDIT, 4), "audit.cs": (C_SHARP_AUDIT, 3)}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, (source, threshold) in cases.items():
                with self.subTest(name=name):
                    path = write_source(root, name, source)
                    result = self.run_guard(root, str(path), "--config", str(self.config(root, threshold)), "--json")
                    payload = self.read_json(result)
                    self.assertEqual(result.returncode, 0)
                    finding = payload["guards"]["complexity"]["findings"][0]
                    self.assertEqual((finding["measured"], finding["state"]), (threshold, "pass"))
                    self.assertEqual(payload["requiredPolicies"], [])

    def test_malformed_python_and_csharp_are_public_exit_three(self) -> None:
        sources = {"broken.py": "def broken(x):\n match x:\n  case x if:\n   pass\n",
                   "broken.cs": "class C { int F(int x) => x switch { 1 when => 1, _ => 0 }; }"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in sources.items():
                with self.subTest(name=name):
                    result = self.run_guard(root, str(write_source(root, name, source)), "--json")
                    self.assertEqual(result.returncode, 3)
                    self.assertEqual(set(self.read_json(result)), {"error"})


if __name__ == "__main__":
    unittest.main()
