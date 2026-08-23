from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import CodeGuardTestCase, write_config

from agent_code_guard.analysis import SyntaxAnalysisError, analyze_files


def write_source(root: Path, source: str, name: str = "audit.go") -> Path:
    path = root / name
    path.write_text(source, encoding="utf-8")
    return path


def owned(facts, callable_fact, collection: str):
    return [item for item in getattr(facts, collection) if item.callable_key == callable_fact.key]


class GoReceiverCallbackFactTests(unittest.TestCase):
    def test_same_named_methods_qualify_callbacks_and_preserve_boundaries(self) -> None:
        source = '''package sample

type A struct{}
type B struct{}

func (a A) Run() {
    _ = func() {
        if ready {
            work()
        }
    }
}

func (b B) Run() {
    _ = func() {
        if ready {
            work()
        }
    }
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = write_source(Path(temp), source)
            facts = analyze_files([path])
            self.assertEqual(facts, analyze_files([path]))
            self.assertEqual([item.identity for item in facts.callables], [
                "sample.A.Run", "sample.A.Run.<callback@7:9>",
                "sample.B.Run", "sample.B.Run.<callback@15:9>",
            ])
            authored = path.read_bytes()
            callbacks = [item for item in facts.callables if item.boundary_kind == "callback"]
            for callback, literal in zip(callbacks, (b"func() {\n        if ready", b"func() {\n        if ready")):
                parent = next(item for item in facts.callables if item.key == callback.parent_key)
                self.assertEqual(callback.parent_callable, parent.identity)
                self.assertEqual(callback.key.identity, callback.identity)
                self.assertEqual(callback.parent_key, parent.key)
                self.assertEqual(callback.boundary_kind, "callback")
                actual = authored[callback.source_range.start.byte_offset:callback.source_range.end.byte_offset]
                self.assertTrue(actual.startswith(literal))
                self.assertTrue(actual.endswith(b"}"))
                self.assertEqual(owned(facts, parent, "decisions"), [])
                self.assertEqual([item.provider_kind for item in owned(facts, callback, "decisions")],
                                 ["if_statement"])
                self.assertEqual([item.provider_kind for item in owned(facts, callback, "controls")],
                                 ["if_statement"])

    def test_receiver_normalization_package_free_function_and_callback_locations(self) -> None:
        source = '''package workers

type Runner struct{}

func (r Runner) Value() { _ = func() {} }
func (receiver *Runner) Pointer() { _ = func() {} }
func (r Runner) Many() {
    first := func() {}
    second := func() {}
    _ = first
    _ = second
}
func Free() { _ = func() {} }
'''
        with tempfile.TemporaryDirectory() as temp:
            facts = analyze_files([write_source(Path(temp), source, "different_name.go")])
            self.assertEqual([item.identity for item in facts.callables], [
                "workers.Runner.Value", "workers.Runner.Value.<callback@5:32>",
                "workers.Runner.Pointer", "workers.Runner.Pointer.<callback@6:42>",
                "workers.Runner.Many", "workers.Runner.Many.<callback@8:14>",
                "workers.Runner.Many.<callback@9:15>",
                "workers.Free", "workers.Free.<callback@13:19>",
            ])

    def test_nested_function_literals_form_receiver_qualified_parent_chain(self) -> None:
        source = '''package sample

type A struct{}

func (a A) Run() {
    outer := func() {
        inner := func() {
            work()
        }
        inner()
    }
    outer()
}
'''
        with tempfile.TemporaryDirectory() as temp:
            facts = analyze_files([write_source(Path(temp), source)])
            method, outer, inner = facts.callables
            self.assertEqual([item.identity for item in facts.callables], [
                "sample.A.Run",
                "sample.A.Run.<callback@6:14>",
                "sample.A.Run.<callback@6:14>.<callback@7:18>",
            ])
            self.assertEqual((outer.parent_callable, outer.parent_key), (method.identity, method.key))
            self.assertEqual((inner.parent_callable, inner.parent_key), (outer.identity, outer.key))

    def test_existing_method_identity_is_unchanged(self) -> None:
        source = "package sample\n\ntype A struct{}\n\nfunc (a A) Run() {}\nfunc (a *A) Stop() {}\n"
        with tempfile.TemporaryDirectory() as temp:
            facts = analyze_files([write_source(Path(temp), source)])
            self.assertEqual([item.identity for item in facts.callables], ["sample.A.Run", "sample.A.Stop"])

    def test_malformed_go_fails_closed(self) -> None:
        source = "package sample\ntype A struct{}\nfunc (a A) Run() { _ = func( { }\n"
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(SyntaxAnalysisError):
            analyze_files([write_source(Path(temp), source)])


class GoReceiverCallbackPublicTests(CodeGuardTestCase):
    def config(self, root: Path) -> Path:
        return write_config(root, {"enabled": False}, guards={
            "callableSize": {"enabled": False},
            "nesting": {"enabled": False},
            "cyclomaticComplexity": {"reviewAt": 1},
            "markdownDocumentSize": {"enabled": False},
            "markdownSectionSize": {"enabled": False},
        })

    def test_json_and_human_output_distinguish_receiver_callbacks_and_keep_metrics(self) -> None:
        source = '''package sample
type A struct{}
type B struct{}
func (a A) Run() { _ = func() { if ready { work() } } }
func (b B) Run() { _ = func() { if ready { work() } } }
func Free() { _ = func() { if ready { work() } } }
'''
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_source(root, source)
            config = self.config(root)
            result = self.run_guard(root, str(path), "--config", str(config), "--json")
            findings = self.read_json(result)["guards"]["complexity"]["findings"]
            callbacks = [item for item in findings if "<callback@" in item["callable"]]
            self.assertEqual(result.returncode, 1)
            self.assertEqual([(item["callable"], item["measured"], item["details"]["decisions"]) for item in callbacks], [
                ("sample.A.Run.<callback@4:24>", 2, {"condition": 1}),
                ("sample.B.Run.<callback@5:24>", 2, {"condition": 1}),
                ("sample.Free.<callback@6:19>", 2, {"condition": 1}),
            ])
            human = self.run_guard(root, str(path), "--config", str(config))
            for item in callbacks:
                self.assertIn(item["callable"], human.stdout)

    def test_malformed_go_is_public_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_source(root, "package sample\nfunc Run() { _ = func( { }\n")
            result = self.run_guard(root, str(path), "--json")
            self.assertEqual(result.returncode, 3)
            self.assertEqual(set(self.read_json(result)), {"error"})


if __name__ == "__main__":
    unittest.main()
