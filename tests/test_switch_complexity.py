from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import CodeGuardTestCase, write_config

from agent_code_guard.analysis import SyntaxAnalysisError, analyze_files


CLASSIC_EQUIVALENTS = {
    ".cpp": "void grouped(int x) { switch (x) { case 1: case 2: work(); break; case 3: default: fallback(); } }",
    ".cs": "class C { void Grouped(int x) { switch (x) { case 1: case 2: Work(); break; case 3: default: Fallback(); } } }",
    ".java": "class C { void grouped(int x) { switch (x) { case 1: case 2: work(); break; case 3: default: fallback(); } } }",
    ".js": "function grouped(x) { switch (x) { case 1: case 2: work(); break; case 3: default: fallback(); } }",
    ".ts": "function grouped(x: number) { switch (x) { case 1: case 2: work(); break; case 3: default: fallback(); } }",
}

PROVIDER_KINDS = {
    ".cpp": "case_statement",
    ".cs": "switch_section",
    ".java": "switch_block_statement_group",
    ".js": "switch_case",
    ".ts": "switch_case",
}


def write_source(root: Path, suffix: str, source: str, stem: str = "switches") -> Path:
    path = root / f"{stem}{suffix}"
    path.write_text(source, encoding="utf-8")
    return path


def switch_arms(facts, callable_fact=None):
    return [item for item in facts.decisions if item.category == "switch_arm"
            and (callable_fact is None or item.callable_key == callable_fact.key)]


class ClassicSwitchFactTests(unittest.TestCase):
    def test_equivalent_classic_switches_emit_two_authored_order_arms(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix, source in CLASSIC_EQUIVALENTS.items():
                with self.subTest(suffix=suffix):
                    path = write_source(root, suffix, source)
                    facts = analyze_files([path])
                    self.assertEqual(facts, analyze_files([path]))
                    callable_fact = facts.callables[0]
                    arms = switch_arms(facts, callable_fact)
                    self.assertEqual(len(arms), 2)
                    self.assertEqual([item.provider_kind for item in arms], [PROVIDER_KINDS[suffix]] * 2)
                    self.assertTrue(all(item.callable_key == callable_fact.key for item in arms))
                    self.assertEqual([item.source_range.start.byte_offset for item in arms],
                                     [source.index("case 1"), source.index("case 3")])
                    self.assertEqual(arms, sorted(arms, key=lambda item: item.source_range.start.byte_offset))

    def test_classic_switch_semantics_coalesce_only_empty_labels(self) -> None:
        cases = {
            "distinct": ("case 1: first(); break; case 2: second(); break; default: fallback();", 2),
            "grouped": ("case 1: case 2: work(); break; default: fallback();", 1),
            "three_grouped": ("case 1: case 2: case 3: work(); break;", 1),
            "default_only": ("default: fallback();", 0),
            "case_default": ("case 1: default: fallback();", 1),
            "executable_fallthrough": ("case 1: prepare(); case 2: finish(); break;", 2),
        }
        wrappers = {
            ".cpp": lambda body: f"void sample(int x) {{ switch (x) {{ {body} }} }}",
            ".cs": lambda body: f"class C {{ void Sample(int x) {{ switch (x) {{ {body} }} }} }}",
            ".java": lambda body: f"class C {{ void sample(int x) {{ switch (x) {{ {body} }} }} }}",
            ".js": lambda body: f"function sample(x) {{ switch (x) {{ {body} }} }}",
            ".ts": lambda body: f"function sample(x: number) {{ switch (x) {{ {body} }} }}",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix, wrap in wrappers.items():
                for name, (body, expected) in cases.items():
                    with self.subTest(suffix=suffix, case=name):
                        path = write_source(root, suffix, wrap(body), name)
                        facts = analyze_files([path])
                        self.assertEqual(len(switch_arms(facts)), expected)

    def test_cpp_supported_extensions_are_equivalent_and_generic_header_is_inert(self) -> None:
        source = CLASSIC_EQUIVALENTS[".cpp"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = [write_source(root, suffix, source, f"sample_{suffix[1:]}")
                     for suffix in (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx")]
            generic = write_source(root, ".h", source, "generic")
            facts = analyze_files([*paths, generic])
            self.assertEqual([len(switch_arms(analyze_files([path]))) for path in paths], [2] * 6)
            self.assertNotIn(generic, {item.path for item in facts.files})

    def test_cpp_switch_labels_inside_language_wrappers_remain_visible(self) -> None:
        sources = {
            "nested_block": "void sample(int x) { switch(x) { { case 1: work(); break; } default: break; } }",
            "preprocessor": "void sample(int x) { switch(x) {\n#if FLAG\ncase 1: work(); break;\n#endif\ndefault: break; } }",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in sources.items():
                with self.subTest(name=name):
                    path = write_source(root, ".cpp", source, name)
                    arms = switch_arms(analyze_files([path]))
                    self.assertEqual(len(arms), 1)
                    self.assertEqual(arms[0].source_range.start.byte_offset,
                                     path.read_bytes().index(b"case 1"))

    def test_cpp_wrapper_grouping_distinguishes_empty_labels_from_authored_fallthrough(self) -> None:
        cases = {
            "grouped": ("case 1: { case 2: work(); break; }", 1),
            "fallthrough": ("case 1: { prepare(); case 2: finish(); break; }", 2),
            "control_fallthrough": ("case 1: if (x) { case 2: finish(); break; }", 2),
            "preprocessor_fallthrough": (
                "case 1: {\n#if FLAG\nprepare();\n#endif\ncase 2: finish(); break; }", 2,
            ),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, (body, expected) in cases.items():
                source = f"void sample(int x) {{ switch(x) {{ {body} default: break; }} }}"
                with self.subTest(name=name):
                    path = write_source(root, ".cpp", source, name)
                    arms = switch_arms(analyze_files([path]))
                    self.assertEqual(len(arms), expected)
                    self.assertEqual(arms[0].source_range.start.byte_offset, path.read_bytes().index(b"case 1"))

    def test_nested_switches_and_switch_if_nesting_preserve_structure(self) -> None:
        source = """function nested(x, y) {
  switch (x) {
    case 1:
      if (y) { switch (y) { case 2: case 3: work(); break; default: break; } }
      break;
    default: break;
  }
}
"""
        with tempfile.TemporaryDirectory() as temp:
            path = write_source(Path(temp), ".js", source)
            facts = analyze_files([path])
            self.assertEqual(len(switch_arms(facts)), 2)
            switches = [item for item in facts.controls if item.provider_kind == "switch_statement"]
            condition = next(item for item in facts.controls if item.provider_kind == "if_statement")
            self.assertEqual(condition.parent_control_range, switches[0].source_range)
            self.assertEqual(switches[1].parent_control_range, condition.source_range)

    def test_cpp_and_typescript_nested_switches_normalize_each_container(self) -> None:
        sources = {
            ".cpp": "void nested(int x, int y) { switch(x) { case 1: switch(y) { case 2: case 3: work(); break; default: break; } break; default: break; } }",
            ".ts": "function nested(x: number, y: number) { switch(x) { case 1: switch(y) { case 2: case 3: work(); break; default: break; } break; default: break; } }",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix, source in sources.items():
                with self.subTest(suffix=suffix):
                    facts = analyze_files([write_source(root, suffix, source, "nested")])
                    self.assertEqual(len(switch_arms(facts)), 2)
                    self.assertEqual([item.source_range.start.byte_offset for item in switch_arms(facts)],
                                     [source.index("case 1"), source.index("case 2")])

    def test_switch_decisions_stay_owned_by_child_callables(self) -> None:
        sources = {
            ".cpp": "void owner(){ auto child = [](int x){ switch(x){case 1: case 2: return 1; default: return 0;} }; }",
            ".cs": "class C { void Owner(){ int Child(int x) { switch(x){case 1: case 2: return 1; default: return 0;} } } }",
            ".java": "class C { void owner(){ java.util.function.IntUnaryOperator child = x -> { switch(x){case 1: case 2: return 1; default: return 0;} }; } }",
            ".js": "function owner(){ const child = x => { switch(x){case 1: case 2: return 1; default: return 0;} }; }",
            ".ts": "function owner(){ const child = (x: number) => { switch(x){case 1: case 2: return 1; default: return 0;} }; }",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix, source in sources.items():
                with self.subTest(suffix=suffix):
                    facts = analyze_files([write_source(root, suffix, source, f"owner_{suffix[1:]}")])
                    parent = next(item for item in facts.callables if item.parent_key is None)
                    child = next(item for item in facts.callables if item.parent_key == parent.key)
                    self.assertEqual(switch_arms(facts, parent), [])
                    self.assertEqual(len(switch_arms(facts, child)), 1)

    def test_java_rules_and_csharp_switch_expressions_are_not_double_normalized(self) -> None:
        sources = {
            ".java": "class C { int modern(int x) { return switch (x) { case 1, 2 -> 1; case 3 -> 2; default -> 0; }; } }",
            ".cs": "class C { int Modern(int x) => x switch { 1 or 2 => 1, 3 => 2, _ => 0 }; }",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix, source in sources.items():
                with self.subTest(suffix=suffix):
                    arms = switch_arms(analyze_files([write_source(root, suffix, source, "modern")]))
                    self.assertEqual(len(arms), 2)
                    expected = "switch_rule" if suffix == ".java" else "switch_expression_arm"
                    self.assertEqual([item.provider_kind for item in arms], [expected, expected])

    def test_jsx_and_tsx_inherit_switch_normalization_while_markup_is_inert(self) -> None:
        sources = {
            ".jsx": "const Component = ({x}) => { switch(x){case 1: case 2: work(); break; default: break;} return <main><section><span>{x}</span></section></main>; };",
            ".tsx": "const Component = ({x}: {x: number}) => { switch(x){case 1: case 2: work(); break; default: break;} return <main><section><span>{x}</span></section></main>; };",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix, source in sources.items():
                with self.subTest(suffix=suffix):
                    facts = analyze_files([write_source(root, suffix, source, "component")])
                    self.assertEqual(len(switch_arms(facts)), 1)
                    self.assertFalse(any(item.provider_kind.startswith("jsx_")
                                         for item in (*facts.controls, *facts.decisions)))

    def test_vue_scripts_inherit_normalization_and_preserve_original_coordinates(self) -> None:
        scripts = (
            "<script>",
            '<script lang="ts">',
            '<script setup lang="ts">',
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, opening in enumerate(scripts):
                source = ("<template><div><span>inert</span></div></template>\n" + opening + "\n"
                          "const grouped = (x: number) => { switch(x){ case 1: case 2: return 1; default: return 0; } };\n"
                          "</script>\n<style>.x { color: red; }</style>\n")
                if opening == "<script>":
                    source = source.replace("(x: number)", "(x)")
                with self.subTest(opening=opening):
                    path = write_source(root, ".vue", source, f"Component{index}")
                    facts = analyze_files([path])
                    self.assertEqual(facts, analyze_files([path]))
                    arm = switch_arms(facts)[0]
                    self.assertEqual(arm.source_range.start.byte_offset, path.read_bytes().index(b"case 1"))
                    self.assertEqual(arm.callable_key.path, path)
                    self.assertEqual(facts.callables[0].embedded_language,
                                     "javascript" if opening == "<script>" else "typescript")
                    self.assertFalse(any(item.provider_kind in {"element", "style_element"}
                                         for item in (*facts.controls, *facts.decisions)))

    def test_representative_malformed_classic_switch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_source(Path(temp), ".js", "function broken(x) { switch (x) { case 1:")
            with self.assertRaises(SyntaxAnalysisError):
                analyze_files([path])


class ClassicSwitchPublicTests(CodeGuardTestCase):
    def test_exact_audit_regressions_report_normalized_measurement_and_breakdown(self) -> None:
        sources = {
            "grouped.js": (
                "function grouped(x) { switch (x) { case 1: case 2: return 2; default: return 0; } }",
                2, 1,
            ),
            "stronger.js": (
                "function stronger(x) { switch (x) { case 1: case 2: break; case 3: default: return 0; } }",
                3, 2,
            ),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = write_config(root, {"enabled": False}, guards={
                "callableSize": {"enabled": False},
                "nesting": {"enabled": False},
                "cyclomaticComplexity": {"reviewAt": 1},
                "markdownDocumentSize": {"enabled": False},
                "markdownSectionSize": {"enabled": False},
            })
            for name, (source, measured, count) in sources.items():
                with self.subTest(name=name):
                    path = write_source(root, ".js", source, Path(name).stem)
                    first = self.run_guard(root, str(path), "--config", str(config), "--json")
                    second = self.run_guard(root, str(path), "--config", str(config), "--json")
                    payload = self.read_json(first)
                    self.assertEqual(payload, self.read_json(second))
                    finding = payload["guards"]["complexity"]["findings"][0]
                    self.assertEqual(first.returncode, 1)
                    self.assertEqual(finding["measured"], measured)
                    self.assertEqual(finding["details"]["decisions"], {"switch_arm": count})
                    self.assertEqual(payload["requiredPolicies"], ["complexity"])

    def test_malformed_classic_switch_is_public_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_source(root, ".js", "function broken(x) { switch (x) { case 1:", "broken")
            result = self.run_guard(root, str(path), "--json")
            self.assert_syntax_unavailable(result, path.name)


if __name__ == "__main__":
    unittest.main()
