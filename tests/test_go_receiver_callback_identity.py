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
            for i := 0; i < 1; i++ {
                work()
            }
        }
    }
}

func (b B) Run() {
    _ = func() {
        if ready {
            for i := 0; i < 1; i++ {
                work()
            }
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
                "sample.B.Run", "sample.B.Run.<callback@17:9>",
            ])
            authored = path.read_bytes()
            callbacks = [item for item in facts.callables if item.boundary_kind == "callback"]
            first_start = authored.index(b"func()")
            expected_starts = [first_start, authored.index(b"func()", first_start + 1)]
            newline = b"\r\n" if b"\r\n" in authored else b"\n"
            literal = newline.join((
                b"func() {", b"        if ready {", b"            for i := 0; i < 1; i++ {",
                b"                work()", b"            }", b"        }", b"    }",
            ))
            for callback, start_line, start_offset in zip(callbacks, (7, 17), expected_starts):
                parent = next(item for item in facts.callables if item.key == callback.parent_key)
                self.assertEqual(callback.parent_callable, parent.identity)
                self.assertEqual(callback.key.identity, callback.identity)
                self.assertEqual((callback.key.path, callback.key.embedded_language, callback.key.source_range),
                                 (callback.path, "go", callback.source_range))
                self.assertEqual(callback.parent_key, parent.key)
                self.assertEqual(callback.boundary_kind, "callback")
                self.assertEqual(callback.source_range.physical_loc, 7)
                self.assertEqual(
                    (callback.source_range.start.line, callback.source_range.start.byte_column,
                     callback.source_range.start.byte_offset, callback.source_range.end.line,
                     callback.source_range.end.byte_column, callback.source_range.end.byte_offset),
                    (start_line, 9, start_offset, start_line + 6, 6, start_offset + len(literal)),
                )
                actual = authored[callback.source_range.start.byte_offset:callback.source_range.end.byte_offset]
                self.assertEqual(actual, literal)
                self.assertEqual(owned(facts, parent, "decisions"), [])
                decisions = owned(facts, callback, "decisions")
                self.assertEqual([item.provider_kind for item in decisions], ["if_statement", "for_statement"])
                self.assertEqual(1 + len(decisions), 3)
                controls = owned(facts, callback, "controls")
                self.assertEqual([item.provider_kind for item in controls], ["if_statement", "for_statement"])
                self.assertEqual([item.parent_control_range for item in controls], [None, controls[0].source_range])
                self.assertTrue(all(item.increases_nesting for item in controls))
                self.assertEqual(len(controls), 2)

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
                "workers.Runner.Value", "workers.Runner.Value.<callback@5:31>",
                "workers.Runner.Pointer", "workers.Runner.Pointer.<callback@6:41>",
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

    def test_generic_receiver_keeps_existing_textual_normalization(self) -> None:
        source = "package sample\n\ntype A[T any] struct{}\n\nfunc (a A[T]) Run() { _ = func() {} }\n"
        with tempfile.TemporaryDirectory() as temp:
            facts = analyze_files([write_source(Path(temp), source)])
            self.assertEqual([item.identity for item in facts.callables], [
                "sample.A[T].Run", "sample.A[T].Run.<callback@5:27>",
            ])

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
            self.assert_syntax_unavailable(result, path.name)


if __name__ == "__main__":
    unittest.main()
