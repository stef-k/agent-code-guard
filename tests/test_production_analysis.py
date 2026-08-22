from __future__ import annotations

import dataclasses
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "skills" / "code-guard" / "scripts"))

from analysis import (  # noqa: E402
    ProviderUnavailableError, SyntaxAnalysisError, TreeSitterProvider, analyze_files,
)
from analysis.regions import executable_regions  # noqa: E402


FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analyzers"


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
                "let second = function (x: number) { return x; };\n"
                "var third = function (x: number) { return x; };\n"
                "function owner() { return [1].map((x) => x + 1); }\n"
                "interface Contract { run(value: number): void; }\n"
                "type Handler = (value: number) => number;\n",
                encoding="utf-8",
            )
            facts = analyze_files([path])
            by_identity = {item.identity: item for item in facts.callables}
            self.assertEqual({"owners.first", "owners.second", "owners.third"} - set(by_identity), set())
            self.assertEqual([by_identity[name].source_range.start_line for name in (
                "owners.first", "owners.second", "owners.third",
            )], [1, 2, 3])
            callback = next(item for item in facts.callables if "<callback@4:" in item.identity)
            self.assertEqual((callback.parent_callable, callback.boundary_kind), ("owners.owner", "callback"))
            self.assertNotIn("run", {item.identity.rsplit(".", 1)[-1] for item in facts.callables})
            self.assertEqual(facts, analyze_files([path]))

    def test_jsx_markup_is_not_control_flow_but_expressions_are_decisions(self) -> None:
        facts = analyze_files([FIXTURES / "tsx" / "components.tsx"])
        self.assertNotIn("jsx_element", {item.provider_kind for item in facts.controls})
        self.assertTrue({"ternary", "short_circuit_boolean"} & {item.category for item in facts.decisions})


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


class ProviderContractTests(unittest.TestCase):
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

        with self.assertRaisesRegex(ProviderUnavailableError, "supported language 'python'.*missing python"):
            analyze_files([FIXTURES / "python" / "callables.py"], TreeSitterProvider(unavailable))


if __name__ == "__main__":
    unittest.main()
