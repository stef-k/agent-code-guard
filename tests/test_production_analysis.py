from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from helpers import REPO_ROOT, analyze_source_paths as analyze_files

from agent_code_guard.analysis import (
    ProviderUnavailableError, SyntaxAnalysisError, TreeSitterProvider,
)
from agent_code_guard.analysis.adapters import _callable_range
from agent_code_guard.analysis.facts import SourcePoint
from agent_code_guard.analysis.regions import ExecutableRegion, executable_regions


FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analyzers"


def _measurements(facts, identity: str) -> tuple[int, int, int]:
    """Derive validation-only LOC, nesting, and complexity from normalized facts."""
    callable_fact = next(item for item in facts.callables if item.identity == identity)
    controls = [item for item in facts.controls if item.callable_key == callable_fact.key]
    by_range = {item.source_range: item for item in controls}

    def depth(control) -> int:
        value = int(control.increases_nesting)
        parent = by_range.get(control.parent_control_range)
        return value + (depth(parent) if parent is not None else 0)

    nesting = max((depth(item) for item in controls), default=0)
    decisions = sum(item.callable_key == callable_fact.key for item in facts.decisions)
    return callable_fact.source_range.physical_loc, nesting, 1 + decisions


class ProductionParityTests(unittest.TestCase):
    def test_representative_first_wave_files_produce_provider_neutral_facts(self) -> None:
        cases = {
            "python/decisions.py": "decisions.deeply_nested",
            "go/decisions.go": "sample.DeeplyNested",
            "kotlin/decisions.kt": "sample.deeplyNested",
            "csharp/Decisions.cs": "Sample.Decisions.DeeplyNested",
            "java/Decisions.java": "sample.Decisions.deeplyNested",
            "javascript/decisions.js": "decisions.deeplyNested",
            "typescript/decisions.ts": "decisions.typedDecisions",
            "jsx/components.jsx": "components.Card",
            "tsx/components.tsx": "components.UserCard",
            "vue/Setup.vue": "Setup.calculate",
        }
        for relative, identity in cases.items():
            with self.subTest(source=relative):
                facts = analyze_files([FIXTURES / relative])
                self.assertIn(identity, {item.identity for item in facts.callables})
                self.assertTrue(facts.decisions)
                self.assertTrue(all(not hasattr(item, "tree") for item in facts.callables))

    def test_facts_are_immutable_and_keep_ranges_not_computed_metrics(self) -> None:
        facts = analyze_files([FIXTURES / "python" / "decisions.py"])
        callable_fact = facts.callables[0]
        self.assertGreater(callable_fact.source_range.physical_loc, 0)
        self.assertFalse(hasattr(callable_fact, "nesting_depth"))
        self.assertFalse(hasattr(callable_fact, "cyclomatic_complexity"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            callable_fact.identity = "changed"

    def test_analyzer_uses_only_selected_files_and_ignores_unsupported_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            selected = root / "selected.py"
            selected.write_text("def selected():\n    return 1\n", encoding="utf-8")
            (root / "not-selected.py").write_text("def hidden():\n    return 1\n", encoding="utf-8")
            notes = root / "notes.txt"
            notes.write_text("not syntax", encoding="utf-8")
            facts = analyze_files([selected, notes])
            self.assertEqual([item.path for item in facts.files], [selected])
            self.assertEqual([item.identity for item in facts.callables], ["selected.selected"])

    def test_js_assignment_ownership_callback_boundaries_and_bodyless_typescript(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "owners.ts"
            path.write_text(
                "const first = (x: number) => x;\n"
                "let secondArrow = (x: number) => x;\n"
                "let second = function (x: number) { return x; };\n"
                "var third = function (x: number) { return x; };\n"
                "function owner() { return [1].map((x) => x + 1); }\n"
                "interface Contract { run(value: number): void; }\n"
                "type Handler = (value: number) => number;\n",
                encoding="utf-8",
            )
            facts = analyze_files([path])
            by_identity = {item.identity: item for item in facts.callables}
            self.assertEqual({"owners.first", "owners.secondArrow", "owners.second", "owners.third"} - set(by_identity), set())
            self.assertEqual([by_identity[name].source_range.start_line for name in (
                "owners.first", "owners.secondArrow", "owners.second", "owners.third",
            )], [1, 2, 3, 4])
            callback = next(item for item in facts.callables if "<callback@5:" in item.identity)
            self.assertEqual((callback.parent_callable, callback.boundary_kind), ("owners.owner", "callback"))
            self.assertNotIn("run", {item.identity.rsplit(".", 1)[-1] for item in facts.callables})
            self.assertEqual(facts, analyze_files([path]))

    def test_jsx_markup_is_not_control_flow_but_expressions_are_decisions(self) -> None:
        facts = analyze_files([FIXTURES / "tsx" / "components.tsx"])
        self.assertNotIn("jsx_element", {item.provider_kind for item in facts.controls})
        categories = {item.category for item in facts.decisions}
        self.assertIn("ternary", categories)
        self.assertNotIn("short_circuit_boolean", categories)

    def test_callable_keys_disambiguate_duplicate_vue_lexical_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Duplicate.vue"
            path.write_text(
                "<script>const run = () => { if (true) return 1; };</script>\n"
                "<script>const run = () => { if (false) return 2; };</script>\n",
                encoding="utf-8",
            )
            facts = analyze_files([path])
            self.assertEqual([item.identity for item in facts.callables], ["Duplicate.run", "Duplicate.run"])
            self.assertEqual(len({item.key for item in facts.callables}), 2)
            self.assertEqual({item.callable_key for item in facts.controls}, {item.key for item in facts.callables})

    def test_structural_facts_preserve_elif_and_normalize_executable_switch_arms(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            python_path = Path(temp) / "branches.py"
            python_path.write_text(
                "def choose(x):\n    if x == 1:\n        return 1\n    elif x == 2:\n        return 2\n",
                encoding="utf-8",
            )
            controls = analyze_files([python_path]).controls
            elif_fact = next(item for item in controls if item.provider_kind == "elif_clause")
            self.assertFalse(elif_fact.increases_nesting)
            self.assertIsNotNone(elif_fact.parent_control_range)

            js_path = Path(temp) / "switches.js"
            js_path.write_text(
                "function choose(x) { switch (x) { case 1: case 2: break; case 3: default: break; } }",
                encoding="utf-8",
            )
            arms = [item for item in analyze_files([js_path]).decisions if item.category == "switch_arm"]
            self.assertEqual(len(arms), 2)

    def test_short_circuit_boolean_expressions_are_not_complexity_decisions(self) -> None:
        cases = {
            ".js":
                "function sample(a, b, c, d) {\n"
                "  if (a && b && c) return 1;\n"
                "  const mixed = (a && b) || (c && d);\n"
                "  const nestedCall = a && Boolean(b || c);\n"
                "  return a ? (b && c) : (c || d);\n"
                "}\n",
            ".py":
                "def sample(a, b, c, d):\n"
                "    if a and b and c:\n"
                "        return 1\n"
                "    mixed = (a and b) or (c and d)\n"
                "    nested_call = a and bool(b or c)\n"
                "    return (b and c) if a else (c or d)\n",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix, source in cases.items():
                with self.subTest(suffix=suffix):
                    path = root / f"boolean{suffix}"
                    path.write_text(source, encoding="utf-8")
                    facts = analyze_files([path])
                    boolean_facts = [item for item in facts.decisions if item.category == "short_circuit_boolean"]
                    self.assertEqual(boolean_facts, [])

    def test_mainstream_lambdas_are_independent_coordinate_owned_callables(self) -> None:
        cases = {
            ".kt": (
                "package sample\nfun owner(values: List<Int>) {\n"
                "  values.map { value -> if (value > 0) value else 0 }\n"
                "  values.map { outer -> values.map { inner -> if (inner > outer) inner else outer } }\n"
                "}\n",
                "sample.owner", 4,
            ),
            ".cs": (
                "class Sample { void Owner(int[] values) {\n"
                "  System.Func<int, int> first = value => value > 0 ? value : 0;\n"
                "  System.Func<int, int> second = async value => { if (value > 0) return value; return 0; };\n"
                "  System.Func<int, int> third = delegate(int value) { while (value > 0) value--; return value; };\n"
                "} }\n",
                "Sample.Owner", 4,
            ),
            ".go": (
                "package sample\nfunc Owner(values []int) {\n"
                "  first := func(value int) int { if value > 0 { return value }; return 0 }\n"
                "  _ = func() { go func() { for len(values) > 0 { return } }() }\n"
                "  _ = first\n}\n",
                "sample.Owner", 4,
            ),
            ".java": (
                "package sample; class Sample { void owner(java.util.List<Integer> values) {\n"
                "  values.stream().map(value -> value > 0 ? value : 0);\n"
                "  values.stream().map(outer -> values.stream().map(inner -> { if (inner > outer) return inner; return outer; }));\n"
                "} }\n",
                "sample.Sample.owner", 4,
            ),
            ".py": (
                "def owner(values):\n"
                "    first = lambda value: value if value > 0 else 0\n"
                "    second = lambda value: (lambda inner: inner and value)(value)\n"
                "    return first, second\n",
                "owner.owner", 4,
            ),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suffix, (source, owner_identity, expected_callables) in cases.items():
                with self.subTest(suffix=suffix):
                    path = root / f"owner{suffix}"
                    path.write_text(source, encoding="utf-8")
                    facts = analyze_files([path])
                    self.assertEqual(facts, analyze_files([path]))
                    owner = next(item for item in facts.callables if item.identity == owner_identity)
                    callbacks = [item for item in facts.callables if item.boundary_kind == "callback"]
                    self.assertEqual(len(facts.callables), expected_callables)
                    self.assertTrue(callbacks)
                    self.assertEqual(len({item.key for item in callbacks}), len(callbacks))
                    self.assertTrue(all("<callback@" in item.identity for item in callbacks))
                    self.assertFalse(any(item.callable_key == owner.key for item in facts.decisions))
                    self.assertTrue(any(item.callable_key in {callback.key for callback in callbacks}
                                        for item in facts.decisions))
                    self.assertTrue(all(item.parent_key is not None for item in callbacks))


class RegionAndVueTests(unittest.TestCase):
    def test_ordinary_region_is_identity_mapped(self) -> None:
        path = FIXTURES / "python" / "callables.py"
        source = path.read_bytes()
        region = executable_regions(path, TreeSitterProvider())[0]
        self.assertEqual((region.original_path, region.language, region.source, region.original_source, region.original_byte_offset),
                         (path, "python", source, source, 0))
        self.assertEqual((region.original_point(0, 0).line, region.original_point(0, 0).byte_column), (1, 1))

    def test_vue_dispatch_multiple_regions_same_line_and_unicode_byte_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Mixed.vue"
            path.write_text(
                '<template>é Ελληνικά</template>\n<script>const plain = () => 1;</script>\n'
                '<script setup lang="typescript">const typed = (x: number) => x ? 1 : 0;</script>\n'
                '<style>.x {}</style>\n', encoding="utf-8",
            )
            facts = analyze_files([path])
            self.assertEqual([(item.identity, item.embedded_language, item.source_range.start_line) for item in facts.callables], [
                ("Mixed.plain", "javascript", 2), ("Mixed.typed", "typescript", 3),
            ])
            self.assertEqual(facts.callables[0].source_range.start.byte_offset, path.read_bytes().index(b"const plain"))
            self.assertEqual(facts.callables[0].source_range.start.byte_column, len(b"<script>") + 1)

    def test_vue_language_aliases_and_setup_dispatch(self) -> None:
        cases = [("", "javascript"), (' lang="js"', "javascript"), (' lang="javascript"', "javascript"),
                 (' setup lang="ts"', "typescript"), (' lang="typescript"', "typescript")]
        with tempfile.TemporaryDirectory() as temp:
            for index, (attributes, expected) in enumerate(cases):
                with self.subTest(attributes=attributes):
                    path = Path(temp) / f"Alias{index}.vue"
                    path.write_text(f"<script{attributes}>const value = () => 1;</script>", encoding="utf-8")
                    self.assertEqual(analyze_files([path]).callables[0].embedded_language, expected)

    def test_vue_rejects_unsupported_external_and_malformed_scripts(self) -> None:
        cases = [
            ('<script lang="coffee">const brew = () => 1;</script>', "unsupported Vue script language"),
            ('<script src="./foo.ts"></script>', "external Vue script regions are unsupported"),
            ('<script lang="ts">const broken = (: number) => 1;</script>', "syntax tree contains errors"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            for index, (source, message) in enumerate(cases):
                path = Path(temp) / f"Bad{index}.vue"
                path.write_text(source, encoding="utf-8")
                with self.subTest(message=message), self.assertRaisesRegex(SyntaxAnalysisError, message):
                    analyze_files([path])

    def test_malformed_ordinary_source_fails_without_partial_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "broken.py"
            path.write_text("def broken(:\n    pass\n", encoding="utf-8")
            with self.assertRaisesRegex(SyntaxAnalysisError, "embedded python syntax tree contains errors"):
                analyze_files([path])


class ProviderContractTests(unittest.TestCase):
    def test_callable_range_uses_each_native_byte_offset_once(self) -> None:
        class Node:
            start_reads = 0
            end_reads = 0

            @property
            def start_byte(self):
                self.start_reads += 1
                return 17

            @property
            def end_byte(self):
                self.end_reads += 1
                return 33

        node = Node()
        region = SimpleNamespace(
            language="csharp",
            original_point_at_byte=lambda offset: SourcePoint(offset // 7 + 1, offset % 7 + 1, offset),
        )

        source_range = _callable_range(node, region)

        self.assertEqual((node.start_reads, node.end_reads), (1, 1))
        self.assertEqual((source_range.start.line, source_range.end.line), (3, 5))

        node.start_reads = node.end_reads = 0
        source = b"xxxxxx\n" * 6
        executable = ExecutableRegion(Path("sample.cs"), "csharp", source, source)
        mapped = executable.original_range(node)
        self.assertEqual((node.start_reads, node.end_reads), (1, 1))
        self.assertEqual((mapped.start.line, mapped.end.line), (3, 5))

    def test_provider_caches_parser_instances_by_language(self) -> None:
        from tree_sitter_language_pack import get_parser
        created: list[str] = []

        def factory(language: str):
            created.append(language)
            return get_parser(language)

        provider = TreeSitterProvider(factory)
        analyze_files([FIXTURES / "javascript" / "callables.js", FIXTURES / "javascript" / "decisions.js",
                       FIXTURES / "typescript" / "callables.ts"], provider)
        self.assertEqual(created, ["javascript", "typescript"])

    def test_each_region_is_parsed_once_and_facts_are_reused_without_parsing(self) -> None:
        class CountingProvider:
            def __init__(self):
                self.inner = TreeSitterProvider()
                self.calls: list[str] = []

            def parse(self, language: str, source: bytes):
                self.calls.append(language)
                return self.inner.parse(language, source)

        provider = CountingProvider()
        facts = analyze_files([FIXTURES / "vue" / "Setup.vue"], provider)
        self.assertEqual(provider.calls, ["vue", "typescript", "typescript"])
        consumers = [lambda value: value.callables, lambda value: value.controls, lambda value: value.decisions]
        self.assertTrue(all(consumer(facts) is not None for consumer in consumers))
        self.assertEqual(provider.calls, ["vue", "typescript", "typescript"])

    def test_supported_language_provider_failure_is_deterministic(self) -> None:
        def unavailable(language: str):
            raise LookupError(f"missing {language}")

        with self.assertRaisesRegex(ProviderUnavailableError, "supported language 'python'.*reinstall Agent Code Guard"):
            analyze_files([FIXTURES / "python" / "callables.py"], TreeSitterProvider(unavailable))


class SecondWaveLanguageTests(unittest.TestCase):
    def test_cpp_callables_preprocessor_and_exact_measurements(self) -> None:
        facts = analyze_files([FIXTURES / "cpp" / "second_wave.cpp"])
        identities = {item.identity for item in facts.callables}
        self.assertTrue({
            "second_wave.choose", "second_wave.Worker.Worker", "second_wave.Worker.~Worker",
            "second_wave.Worker.operator()", "second_wave.Worker.Nested.run", "second_wave.stable",
            "second_wave.consume.<callback@40:9>", "second_wave.configured",
        }.issubset(identities))
        self.assertEqual(_measurements(facts, "second_wave.choose"), (9, 2, 3))
        self.assertEqual(_measurements(facts, "second_wave.Worker.operator()"), (3, 0, 2))
        self.assertFalse(any(item.provider_kind.startswith("preproc") for item in facts.decisions))

    def test_rust_patterns_closures_and_exact_measurements(self) -> None:
        facts = analyze_files([FIXTURES / "rust" / "second_wave.rs"])
        by_identity = {item.identity: item for item in facts.callables}
        self.assertTrue({"second_wave.evaluate", "second_wave.Work.default_run",
                         "second_wave.Worker.default_run", "second_wave.closures.stable"}.issubset(by_identity))
        callback = next(item for item in facts.callables if "<callback@24:13>" in item.identity)
        self.assertEqual((callback.parent_callable, callback.boundary_kind), ("second_wave.closures", "callback"))
        self.assertEqual(_measurements(facts, "second_wave.evaluate"), (12, 3, 8))
        self.assertIn("pattern_guard", {item.category for item in facts.decisions})

    def test_php_mixed_source_preserves_original_coordinates_and_ignores_html(self) -> None:
        path = FIXTURES / "php" / "Mixed.php"
        facts = analyze_files([path])
        self.assertEqual(facts.files[0].region_count, 1)
        by_identity = {item.identity: item for item in facts.callables}
        self.assertEqual((by_identity["Mixed.foo"].source_range.start_line,
                          by_identity["Mixed.bar"].source_range.start_line), (4, 26))
        self.assertEqual(by_identity["Mixed.bar"].source_range.start.byte_offset,
                         path.read_bytes().index(b"function bar"))
        self.assertTrue(all(item.path == path and item.embedded_language == "php" for item in facts.callables))
        self.assertFalse(any(item.provider_kind in {"text", "text_interpolation"}
                             for item in (*facts.controls, *facts.decisions)))
        self.assertEqual(_measurements(facts, "Mixed.foo"), (6, 1, 3))
        callback = next(item for item in facts.callables if item.boundary_kind == "callback")
        self.assertEqual(callback.parent_callable, "Mixed.bar")

    def test_swift_guard_patterns_closures_and_exact_measurements(self) -> None:
        facts = analyze_files([FIXTURES / "swift" / "second_wave.swift"])
        identities = {item.identity for item in facts.callables}
        self.assertTrue({"second_wave.evaluate", "second_wave.Worker.init", "second_wave.Worker.run",
                         "second_wave.Worker.extra", "second_wave.Work.provided", "second_wave.stable"}.issubset(identities))
        self.assertEqual(_measurements(facts, "second_wave.evaluate"), (13, 2, 8))
        guard = next(item for item in facts.controls if item.provider_kind == "guard_statement")
        self.assertEqual((guard.category, guard.increases_nesting), ("condition", True))
        self.assertIn("pattern_guard", {item.category for item in facts.decisions})

    def test_dart_async_local_closures_null_aware_and_exact_measurements(self) -> None:
        facts = analyze_files([FIXTURES / "dart" / "second_wave.dart"])
        by_identity = {item.identity: item for item in facts.callables}
        self.assertTrue({"second_wave.evaluate", "second_wave.local", "second_wave.stable",
                         "second_wave.Worker.Worker", "second_wave.Worker.run"}.issubset(by_identity))
        self.assertEqual(by_identity["second_wave.local"].parent_callable, "second_wave.evaluate")
        self.assertEqual(_measurements(facts, "second_wave.evaluate"), (14, 3, 5))
        self.assertNotIn("fallback", {item.category for item in facts.decisions})

    def test_all_second_wave_languages_reject_malformed_supported_source(self) -> None:
        cases = {
            ".cpp": "int broken( {",
            ".rs": "fn broken( {",
            ".php": "<?php function broken( { ?>",
            ".swift": "func broken( {",
            ".dart": "void broken( {",
        }
        with tempfile.TemporaryDirectory() as temp:
            for suffix, source in cases.items():
                path = Path(temp) / f"broken{suffix}"
                path.write_text(source, encoding="utf-8")
                with self.subTest(suffix=suffix), self.assertRaises(SyntaxAnalysisError):
                    analyze_files([path])

    def test_second_wave_suffix_policy_excludes_ambiguous_generic_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = []
            for suffix in (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"):
                path = root / f"sample{suffix}"
                path.write_text("int run() { return 1; }", encoding="utf-8")
                paths.append(path)
            generic_header = root / "sample.h"
            generic_header.write_text("int run() { return 1; }", encoding="utf-8")
            facts = analyze_files([*paths, generic_header])
            self.assertEqual(len(facts.files), len(paths))

    def test_second_wave_parser_cache_and_parse_once_contract(self) -> None:
        from tree_sitter_language_pack import get_parser
        created = []

        def factory(language: str):
            created.append(language)
            return get_parser(language)

        provider = TreeSitterProvider(factory)
        paths = [FIXTURES / language / filename for language, filename in (
            ("cpp", "second_wave.cpp"), ("rust", "second_wave.rs"), ("php", "Mixed.php"),
            ("swift", "second_wave.swift"), ("dart", "second_wave.dart"),
        )]
        facts = analyze_files([*paths, paths[0]], provider)
        self.assertEqual(created, ["cpp", "rust", "php", "swift", "dart"])
        self.assertTrue(facts.callables)


if __name__ == "__main__":
    unittest.main()
