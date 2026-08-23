from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_code_guard.analysis import SyntaxAnalysisError, analyze_files

from helpers import CodeGuardTestCase


def _measurements(facts, identity: str) -> tuple[int, int, int]:
    callable_fact = next(item for item in facts.callables if item.identity == identity)
    controls = [item for item in facts.controls if item.callable_key == callable_fact.key]
    by_range = {item.source_range: item for item in controls}

    def depth(control) -> int:
        parent = by_range.get(control.parent_control_range)
        return int(control.increases_nesting) + (depth(parent) if parent is not None else 0)

    return (
        callable_fact.source_range.physical_loc,
        max((depth(item) for item in controls), default=0),
        1 + sum(item.callable_key == callable_fact.key for item in facts.decisions),
    )


class DartNamedConstructorFactTests(unittest.TestCase):
    def analyze(self, source: str, name: str = "constructors.dart"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / name
        path.write_text(source, encoding="utf-8")
        return path, analyze_files([path])

    def test_unnamed_named_multiple_classes_methods_and_factory_keep_lexical_identities(self) -> None:
        source = (
            "class A {\n"
            "  A() {}\n"
            "  A.named() {}\n"
            "  A.first() {}\n"
            "  A.second() {}\n"
            "  factory A.factoryNamed() => A();\n"
            "  void run() {}\n"
            "  int value() => 1;\n"
            "}\n"
            "class B {\n"
            "  B.named() {}\n"
            "}\n"
        )
        path, facts = self.analyze(source)
        identities = [item.identity for item in facts.callables]

        self.assertEqual(identities, [
            "constructors.A.A",
            "constructors.A.A.named",
            "constructors.A.A.first",
            "constructors.A.A.second",
            "constructors.A.A.factoryNamed",
            "constructors.A.run",
            "constructors.A.value",
            "constructors.B.B.named",
        ])
        self.assertEqual(facts, analyze_files([path]))
        for callable_fact in facts.callables:
            self.assertEqual(callable_fact.key.identity, callable_fact.identity)
            self.assertEqual(callable_fact.boundary_kind, "callable")
            self.assertIsNone(callable_fact.parent_callable)
            self.assertIsNone(callable_fact.parent_key)

        named = facts.callables[1]
        written_source = path.read_bytes()
        start = written_source.index(b"A.named()")
        end = written_source.index(b"}", start) + 1
        self.assertEqual(
            (
                named.source_range.start.line,
                named.source_range.start.byte_column,
                named.source_range.start.byte_offset,
                named.source_range.end.line,
                named.source_range.end.byte_column,
                named.source_range.end.byte_offset,
                named.source_range.physical_loc,
            ),
            (3, 3, start, 3, 15, end, 1),
        )
        self.assertEqual(named.key.source_range, named.source_range)
        self.assertEqual((named.key.path, named.key.embedded_language), (path, "dart"))

    def test_exact_audit_reproduction_has_distinct_identity_and_unchanged_metrics(self) -> None:
        source = (
            "class C {\n"
            "  C() {\n"
            "    if (ready) {\n"
            "      work();\n"
            "    }\n"
            "  }\n\n"
            "  C.named() {\n"
            "    if (ready) {\n"
            "      work();\n"
            "    }\n"
            "  }\n"
            "}\n"
        )
        _, facts = self.analyze(source, "audit_47.dart")

        self.assertEqual([item.identity for item in facts.callables], ["audit_47.C.C", "audit_47.C.C.named"])
        self.assertEqual(_measurements(facts, "audit_47.C.C"), (5, 1, 2))
        self.assertEqual(_measurements(facts, "audit_47.C.C.named"), (5, 1, 2))
        self.assertEqual(
            {item.callable_identity for item in facts.decisions},
            {"audit_47.C.C", "audit_47.C.C.named"},
        )

    def test_nested_closure_keeps_independent_range_and_metric_ownership(self) -> None:
        source = (
            "class C {\n"
            "  C.named(int x) {\n"
            "    if (x > 0) {\n"
            "      for (final value in values) {\n"
            "        work(value);\n"
            "      }\n"
            "    }\n"
            "    final child = () {\n"
            "      if (ready) {\n"
            "        work();\n"
            "      }\n"
            "    };\n"
            "  }\n"
            "}\n"
        )
        _, facts = self.analyze(source, "nested.dart")
        constructor = next(item for item in facts.callables if item.identity == "nested.C.C.named")
        child = next(item for item in facts.callables if item.identity == "nested.C.child")

        self.assertEqual(child.identity, "nested.C.child")
        self.assertEqual(child.boundary_kind, "nested")
        self.assertEqual((child.parent_callable, child.parent_key), (constructor.identity, constructor.key))
        self.assertEqual(_measurements(facts, constructor.identity), (12, 2, 3))
        self.assertEqual(_measurements(facts, child.identity), (5, 1, 2))
        self.assertEqual(
            {item.callable_key for item in facts.decisions},
            {constructor.key, child.key},
        )

    def test_bodyless_redirecting_and_const_constructors_remain_excluded(self) -> None:
        source = (
            "class C {\n"
            "  C() {}\n"
            "  C.redirecting() : this();\n"
            "  const C.constant();\n"
            "  factory C.redirected() = D.make;\n"
            "}\n"
            "class D {\n"
            "  D.make();\n"
            "}\n"
        )
        _, facts = self.analyze(source)

        self.assertEqual([item.identity for item in facts.callables], ["constructors.C.C"])

    def test_malformed_named_constructor_fails_closed(self) -> None:
        with self.assertRaises(SyntaxAnalysisError):
            self.analyze("class C { C.named( { }", "broken.dart")


class DartNamedConstructorPublicTests(CodeGuardTestCase):
    SOURCE = (
        "class C {\n"
        "  C() {\n"
        "    if (ready) {}\n"
        "  }\n"
        "  C.named() {\n"
        "    if (ready) {}\n"
        "  }\n"
        "}\n"
    )

    def test_public_json_and_human_output_report_distinct_constructor_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "constructors.dart").write_text(self.SOURCE, encoding="utf-8")
            config = root / "code-guard.config.json"
            config.write_text(json.dumps({
                "version": 1,
                "guards": {
                    "callableSize": {"enabled": False},
                    "nesting": {"enabled": False},
                    "cyclomaticComplexity": {"reviewAt": 1},
                },
            }), encoding="utf-8")

            result = self.run_guard(root, "constructors.dart", "--config", str(config), "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            findings = self.read_json(result)["guards"]["complexity"]["findings"]
            self.assertEqual(
                [(item["callable"], item["measured"]) for item in findings],
                [("constructors.C.C", 2), ("constructors.C.C.named", 2)],
            )

            human = self.run_guard(root, "constructors.dart", "--config", str(config))
            self.assertEqual(human.returncode, 1, human.stderr)
            self.assertIn("constructors.C.C.named complexity 2", human.stdout)

    def test_public_command_rejects_malformed_named_constructor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "broken.dart").write_text("class C { C.named( { }", encoding="utf-8")
            result = self.run_guard(root, "broken.dart", "--json")
            self.assertEqual(result.returncode, 3)
            self.assertIn("syntax tree contains errors", self.read_json(result)["error"])


if __name__ == "__main__":
    unittest.main()
