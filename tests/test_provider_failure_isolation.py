from __future__ import annotations

import tempfile
from importlib import import_module
from pathlib import Path
import sys
import types

from tests.helpers import CodeGuardTestCase, REPO_ROOT, write_config

CHECKOUT_PACKAGE = "_issue115_checkout_agent_code_guard"
package = types.ModuleType(CHECKOUT_PACKAGE)
package.__path__ = [str(REPO_ROOT / "src" / "agent_code_guard")]
sys.modules[CHECKOUT_PACKAGE] = package
pipeline = import_module(f"{CHECKOUT_PACKAGE}.analysis.pipeline")
provider_module = import_module(f"{CHECKOUT_PACKAGE}.analysis.provider")
analyze_files_for_runner = pipeline.analyze_files_for_runner
TreeSitterProvider = provider_module.TreeSitterProvider


class ProviderFailureIsolationLifecycleTests(CodeGuardTestCase):
    def create_mixed_selection(self, root: Path) -> Path:
        (root / "valid.py").write_text(
            "def classify(value):\n"
            "    if value:\n"
            "        return 1\n"
            "    return 0\n",
            encoding="utf-8",
        )
        (root / "broken.py").write_text(
            "def broken(:\n    value = 1\n    value = 2\n    value = 3\n", encoding="utf-8",
        )
        (root / "guide.md").write_text("# Guide\n\nUseful text.\n", encoding="utf-8")
        loc_config = {"warnAt": 3, "failAt": 20}
        return write_config(root, loc_config, guards={
            "loc": loc_config,
            "markdownDocumentSize": {"reviewAt": 2},
            "markdownSectionSize": {"reviewAt": 1},
        })

    def test_mixed_public_run_preserves_independent_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.create_mixed_selection(root)

            result = self.run_guard(
                root, "valid.py", "broken.py", "guide.md", "--config", str(config), "--json",
            )

            self.assertEqual(result.returncode, 3, result.stderr)
            data = self.read_json(result)
            self.assertEqual(data["overall"], "incomplete")
            self.assertEqual(data["completedOverall"], "review")
            self.assertEqual(data["scope"], {
                "selected": 3, "analyzed": 3, "inapplicable": 0, "unavailable": 1, "excluded": 0,
            })
            self.assertEqual(
                [(item["path"], item["language"], item["kind"]) for item in data["unavailable"]],
                [("broken.py", "python", "syntax")],
            )
            self.assertIn("embedded python syntax tree contains errors", data["unavailable"][0]["message"])
            self.assertEqual(
                data["requiredPolicies"], ["loc", "markdownDocumentSize", "markdownSectionSize"],
            )
            self.assertEqual(data["guards"]["loc"]["complete"], True)
            for guard_id in ("callableSize", "nesting", "complexity"):
                self.assertEqual(data["guards"][guard_id]["complete"], False)
                self.assertEqual(data["guards"][guard_id]["unavailablePaths"], ["broken.py"])
            for guard_id in ("markdownDocumentSize", "markdownSectionSize"):
                self.assertEqual(data["guards"][guard_id]["complete"], True)
            self.assertEqual(
                {item["path"] for item in data["guards"]["loc"]["findings"]},
                {"valid.py", "broken.py"},
            )
            self.assertTrue(data["guards"]["complexity"]["findings"])
            self.assertEqual(data["guards"]["markdownDocumentSize"]["findings"][0]["path"], "guide.md")
            self.assertEqual(data["guards"]["markdownSectionSize"]["findings"][0]["path"], "guide.md")

    def test_all_output_and_ci_modes_retain_unavailable_context_and_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.create_mixed_selection(root)
            base = ("valid.py", "broken.py", "guide.md", "--config", str(config))
            json_payloads = {}
            for ci in (False, True):
                ci_args = ("--ci",) if ci else ()
                human = self.run_guard(root, *base, *ci_args)
                self.assertEqual(human.returncode, 3, human.stderr)
                lines = human.stdout.splitlines()
                self.assertEqual(
                    lines[0],
                    "INCOMPLETE: 3 selected; 3 analyzed; 0 inapplicable; 1 unavailable; "
                    "0 excluded. Completed findings: REVIEW.",
                )
                self.assertTrue(lines[1].startswith("UNAVAILABLE: broken.py [python syntax] - "))
                self.assertEqual(lines[2], "Incomplete guards: callableSize, nesting, complexity.")
                self.assertTrue(any(line.startswith("REVIEW: valid.py ") for line in lines[3:]))
                self.assertTrue(any(line.startswith("REVIEW: broken.py ") for line in lines[3:]))
                self.assertTrue(any(line.startswith("REVIEW: guide.md ") for line in lines[3:]))
                self.assertTrue(any("section \"Guide\"" in line for line in lines[3:]))
                self.assertIn(
                    "Required policies: loc, markdownDocumentSize, markdownSectionSize", lines,
                )
                for mode, mode_args in (
                    ("full", ("--json",)),
                    ("debug", ("--json", "--json-mode", "debug")),
                    ("compact", ("--json", "--json-mode", "compact")),
                ):
                    result = self.run_guard(root, *base, *ci_args, *mode_args)
                    self.assertEqual(result.returncode, 3, result.stderr)
                    json_payloads[(ci, mode)] = self.read_json(result)
            expected = json_payloads[(False, "full")]["unavailable"]
            self.assertTrue(all(data["unavailable"] == expected for data in json_payloads.values()))
            self.assertEqual(json_payloads[(False, "debug")], json_payloads[(False, "full")])
            self.assertEqual(json_payloads[(True, "debug")], json_payloads[(True, "full")])

    def test_one_file_unavailable_selection_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            result = self.run_guard(root, "broken.py", "--json")
            data = self.read_json(result)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(data["scope"], {
                "selected": 1, "analyzed": 1, "inapplicable": 0, "unavailable": 1, "excluded": 0,
            })
            self.assertEqual(data["unavailable"][0]["path"], "broken.py")


class ProviderFailureIsolationPipelineTests(CodeGuardTestCase):
    def test_provider_failure_records_each_path_and_continues_other_languages(self) -> None:
        from tree_sitter_language_pack import get_parser

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.py"
            second = root / "second.py"
            java = root / "Example.java"
            first.write_text("value = 1\n", encoding="utf-8")
            second.write_text("value = 2\n", encoding="utf-8")
            java.write_text("class Example { int value() { return 1; } }\n", encoding="utf-8")

            def factory(language: str):
                if language == "python":
                    raise LookupError("missing python grammar")
                return get_parser(language)

            result = analyze_files_for_runner(
                [first, second, java], TreeSitterProvider(factory),
            )
            self.assertEqual([item.path for item in result.facts.files], [java])
            self.assertEqual(
                [(item.path, item.language, item.kind) for item in result.unavailable],
                [(first, "python", "provider"), (second, "python", "provider")],
            )
            self.assertTrue(all(item.message == result.unavailable[0].message for item in result.unavailable))

    def test_arbitrary_concrete_parser_exception_still_aborts(self) -> None:
        defect = ZeroDivisionError("programming defect")

        class BrokenParser:
            def parse(self, source: bytes):
                raise defect

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.py"
            path.write_text("value = 1\n", encoding="utf-8")
            with self.assertRaises(ZeroDivisionError) as caught:
                analyze_files_for_runner(
                    [path], TreeSitterProvider(parser_factory=lambda _: BrokenParser()),
                )
            self.assertIs(caught.exception, defect)

    def test_concrete_parser_runtime_failure_is_unavailable(self) -> None:
        class UnavailableParser:
            def parse(self, source: bytes):
                raise RuntimeError("runtime unavailable")

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.py"
            path.write_text("value = 1\n", encoding="utf-8")

            result = analyze_files_for_runner(
                [path], TreeSitterProvider(parser_factory=lambda _: UnavailableParser()),
            )

            self.assertEqual(result.facts.files, ())
            self.assertEqual(
                [(item.path, item.language, item.kind) for item in result.unavailable],
                [(path, "python", "provider")],
            )
            self.assertIn("runtime unavailable", result.unavailable[0].message)


if __name__ == "__main__":
    import unittest

    unittest.main()
