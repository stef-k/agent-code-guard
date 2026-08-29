from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import CodeGuardTestCase, write_config

from agent_code_guard.analysis import SyntaxAnalysisError
from helpers import analyze_source_paths as analyze_files


PLAIN_AUDIT = '''func plainScopes() {
    do {
        do {
            work()
        }
    }
}
'''

SINGLE_CATCH = '''func handled() {
    do {
        try work()
    } catch {
        recover()
    }
}
'''

MULTIPLE_CATCHES = '''func handled() {
    do {
        try work()
    } catch Error.one {
        recoverOne()
    } catch Error.two {
        recoverTwo()
    }
}
'''


def write_source(root: Path, name: str, source: str) -> Path:
    path = root / name
    path.write_text(source, encoding="utf-8")
    return path


def owned(facts, collection: str, callable_fact):
    return [item for item in getattr(facts, collection) if item.callable_key == callable_fact.key]


def authored(path: Path, source_range) -> bytes:
    source = path.read_bytes()
    return source[source_range.start.byte_offset:source_range.end.byte_offset]


class SwiftDoCatchFactTests(unittest.TestCase):
    def test_exact_audit_plain_do_scopes_emit_no_control_or_decision_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_source(Path(temp), "plain.swift", PLAIN_AUDIT)
            facts = analyze_files([path])
            self.assertEqual(facts, analyze_files([path]))
            callable_fact = facts.callables[0]
            self.assertEqual(owned(facts, "controls", callable_fact), [])
            self.assertEqual(owned(facts, "decisions", callable_fact), [])

            nested = write_source(Path(temp), "nested.swift", '''func example() {
    do { do { do { work() } } }
}
''')
            nested_facts = analyze_files([nested])
            self.assertEqual(owned(nested_facts, "controls", nested_facts.callables[0]), [])
            self.assertEqual(owned(nested_facts, "decisions", nested_facts.callables[0]), [])

    def test_single_and_multiple_catches_emit_one_exception_control_and_authored_decisions(self) -> None:
        cases = (
            (SINGLE_CATCH, (
                b"catch {\n        recover()\n    }",
            )),
            (MULTIPLE_CATCHES, (
                b"catch Error.one {\n        recoverOne()\n    }",
                b"catch Error.two {\n        recoverTwo()\n    }",
            )),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, (source, catch_texts) in enumerate(cases):
                catch_count = len(catch_texts)
                with self.subTest(catch_count=catch_count):
                    path = write_source(root, f"caught-{index}.swift", source)
                    facts = analyze_files([path])
                    self.assertEqual(facts, analyze_files([path]))
                    callable_fact = facts.callables[0]
                    controls = owned(facts, "controls", callable_fact)
                    self.assertEqual(len(controls), 1)
                    control = controls[0]
                    self.assertEqual(
                        (control.provider_kind, control.category, control.increases_nesting,
                         control.parent_control_range),
                        ("do_statement", "exception", True, None),
                    )
                    source_bytes = path.read_bytes()
                    newline = b"\r\n" if b"\r\n" in source_bytes else b"\n"
                    expected_control = source_bytes[source_bytes.index(b"do {"):source_bytes.rindex(newline + b"}")]
                    catch_texts = tuple(text.replace(b"\n", newline) for text in catch_texts)
                    self.assertEqual(authored(path, control.source_range), expected_control)
                    self.assertEqual(
                        (control.source_range.start.byte_offset, control.source_range.end.byte_offset),
                        (source_bytes.index(expected_control), source_bytes.index(expected_control) + len(expected_control)),
                    )
                    decisions = owned(facts, "decisions", callable_fact)
                    catches = [item for item in decisions if item.category == "catch"]
                    self.assertEqual(len(catches), catch_count)
                    self.assertEqual([item.provider_kind for item in catches], ["catch_block"] * catch_count)
                    self.assertEqual([authored(path, item.source_range) for item in catches], list(catch_texts))
                    self.assertEqual(
                        [(item.source_range.start.byte_offset, item.source_range.end.byte_offset) for item in catches],
                        [(source_bytes.index(text), source_bytes.index(text) + len(text)) for text in catch_texts],
                    )
                    starts = [item.source_range.start.byte_offset for item in decisions]
                    self.assertEqual(starts, sorted(starts))

    def test_plain_do_composes_with_if_and_real_do_catch_without_changing_parent(self) -> None:
        sources = {
            "plain-if": '''func example(_ x: Int) {
    do { if x > 0 { work() } }
}
''',
            "plain-caught": '''func example() {
    do { do { try work() } catch { recover() } }
}
''',
            "caught-plain-if": '''func example(_ x: Int) {
    do { do { if x > 0 { work() } } } catch { recover() }
}
''',
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in sources.items():
                path = write_source(root, f"{name}.swift", source)
                facts = analyze_files([path])
                controls = owned(facts, "controls", facts.callables[0])
                with self.subTest(name=name):
                    self.assertFalse(any(
                        item.provider_kind == "do_statement" and b"catch" not in authored(path, item.source_range)
                        for item in controls
                    ))
                    if name == "plain-if":
                        self.assertEqual([item.provider_kind for item in controls], ["if_statement"])
                        self.assertIsNone(controls[0].parent_control_range)
                    elif name == "plain-caught":
                        self.assertEqual([item.provider_kind for item in controls], ["do_statement"])
                    else:
                        self.assertEqual([item.provider_kind for item in controls], ["do_statement", "if_statement"])
                        self.assertEqual(controls[1].parent_control_range, controls[0].source_range)

    def test_nested_real_do_catch_preserves_parent_ranges_and_catch_body_control(self) -> None:
        source = '''func example(_ shouldRecover: Bool) {
    do {
        do { try inner() } catch { recoverInner() }
    } catch {
        if shouldRecover { recoverOuter() }
    }
}
'''
        with tempfile.TemporaryDirectory() as temp:
            facts = analyze_files([write_source(Path(temp), "nested.swift", source)])
            controls = owned(facts, "controls", facts.callables[0])
            self.assertEqual([item.provider_kind for item in controls],
                             ["do_statement", "do_statement", "if_statement"])
            outer, inner, condition = controls
            self.assertIsNone(outer.parent_control_range)
            self.assertEqual(inner.parent_control_range, outer.source_range)
            self.assertEqual(condition.parent_control_range, outer.source_range)
            catches = [item for item in owned(facts, "decisions", facts.callables[0]) if item.category == "catch"]
            self.assertEqual(len(catches), 2)

    def test_closures_inside_plain_and_caught_do_remain_independently_owned(self) -> None:
        sources = {
            "plain": '''func owner() {
    do { let child = { if ready { work() } } }
}
''',
            "caught": '''func owner() {
    do { let child = { if ready { work() } } } catch { recover() }
}
''',
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in sources.items():
                facts = analyze_files([write_source(root, f"{name}.swift", source)])
                parent = next(item for item in facts.callables if item.parent_key is None)
                child = next(item for item in facts.callables if item.parent_key == parent.key)
                parent_controls = owned(facts, "controls", parent)
                child_controls = owned(facts, "controls", child)
                with self.subTest(name=name):
                    self.assertEqual(child.parent_callable, parent.identity)
                    self.assertTrue(child.identity.endswith(".owner.child"))
                    self.assertEqual(child.boundary_kind, "nested")
                    self.assertEqual([item.provider_kind for item in child_controls], ["if_statement"])
                    self.assertIsNone(child_controls[0].parent_control_range)
                    self.assertEqual([item.provider_kind for item in parent_controls],
                                     [] if name == "plain" else ["do_statement"])
                    self.assertEqual([item.category for item in owned(facts, "decisions", parent)],
                                     [] if name == "plain" else ["catch"])

    def test_swift_guard_switch_where_and_javascript_do_loop_regressions(self) -> None:
        swift = '''func choose(_ x: Int?, _ retry: Bool) {
    guard let x else { if retry { return }; return }
    switch x {
    case let n where n > 0: work()
    default: return
    }
}
'''
        javascript = "function repeat() { do { work(); } while (ready); }\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            swift_facts = analyze_files([write_source(root, "guard.swift", swift)])
            callable_fact = swift_facts.callables[0]
            controls = owned(swift_facts, "controls", callable_fact)
            self.assertEqual([item.provider_kind for item in controls],
                             ["guard_statement", "if_statement", "switch_statement"])
            self.assertEqual(controls[1].parent_control_range, controls[0].source_range)
            self.assertIsNone(controls[2].parent_control_range)
            self.assertEqual([item.category for item in owned(swift_facts, "decisions", callable_fact)],
                             ["condition", "condition", "switch_arm", "pattern_guard"])
            js_facts = analyze_files([write_source(root, "loop.js", javascript)])
            do_loop = owned(js_facts, "controls", js_facts.callables[0])[0]
            self.assertEqual((do_loop.provider_kind, do_loop.category, do_loop.increases_nesting),
                             ("do_statement", "loop", True))

    def test_malformed_do_catch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_source(Path(temp), "broken.swift", "func broken() { do { try work() } catch {\n")
            with self.assertRaises(SyntaxAnalysisError):
                analyze_files([path])


class SwiftDoCatchPublicTests(CodeGuardTestCase):
    def config(self, root: Path, nesting_at: int, complexity_at: int) -> Path:
        return write_config(root, {"enabled": False}, guards={
            "callableSize": {"enabled": False},
            "nesting": {"reviewAt": nesting_at},
            "cyclomaticComplexity": {"reviewAt": complexity_at},
            "markdownDocumentSize": {"enabled": False},
            "markdownSectionSize": {"enabled": False},
        })

    def test_plain_audit_public_measurement_is_zero_and_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_source(root, "plain.swift", PLAIN_AUDIT)
            result = self.run_guard(root, str(path), "--config", str(self.config(root, 1, 1)), "--json")
            payload = self.read_json(result)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(payload["guards"]["nesting"]["findings"][0]["measured"], 0)
            self.assertEqual(payload["guards"]["complexity"]["findings"][0]["measured"], 1)
            self.assertEqual(payload["requiredPolicies"], [])

    def test_catches_preserve_public_nesting_and_complexity_breakdown(self) -> None:
        cases = ((SINGLE_CATCH, 1, 2), (MULTIPLE_CATCHES, 2, 3))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, (source, catch_count, complexity) in enumerate(cases):
                with self.subTest(catch_count=catch_count):
                    path = write_source(root, f"caught-{index}.swift", source)
                    result = self.run_guard(root, str(path), "--config", str(self.config(root, 1, 1)), "--json")
                    payload = self.read_json(result)
                    self.assertEqual(result.returncode, 1)
                    nesting = payload["guards"]["nesting"]
                    self.assertEqual((nesting["state"], nesting["findings"][0]["measured"],
                                      nesting["findings"][0]["state"]), ("pass", 1, "pass"))
                    finding = payload["guards"]["complexity"]["findings"][0]
                    self.assertEqual((finding["measured"], finding["state"], finding["details"]["decisions"]),
                                     (complexity, "review", {"catch": catch_count}))
                    self.assertEqual(payload["requiredPolicies"], ["complexity"])

    def test_malformed_do_catch_is_public_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_source(root, "broken.swift", "func broken() { do { try work() } catch {\n")
            result = self.run_guard(root, str(path), "--json")
            self.assert_syntax_unavailable(result, path.name)


if __name__ == "__main__":
    unittest.main()
