from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_code_guard.code_guard import run_guards
from agent_code_guard.file_selection import ResolvedScope
from agent_code_guard.guards import markdown_document_size, markdown_section_size
from agent_code_guard.markdown import analyze_files, scan_text

from helpers import CodeGuardTestCase, write_config, write_lines


def args(config: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        config=str(config) if config else None,
        warn=None,
        fail=None,
        include=[],
        exclude=[],
        count_blank_lines=False,
        ignore_comment_lines=False,
    )


class MarkdownScannerTests(unittest.TestCase):
    def test_bounded_heading_and_direct_section_contract(self) -> None:
        text = """preamble

# ATX ###
body
## Child
~~~~ info
# fenced
~~~~
Setext title
------------
tail"""
        fact = scan_text(Path("sample.md"), text)
        self.assertEqual(fact.physical_lines, 11)
        self.assertEqual(
            [(section.heading, section.level, section.start_line, section.end_line, section.physical_lines)
             for section in fact.sections],
            [("ATX", 1, 3, 4, 2), ("Child", 2, 5, 8, 4), ("Setext title", 2, 9, 11, 3)],
        )

    def test_fences_indentation_escapes_and_unclosed_fence_are_deterministic(self) -> None:
        text = """   # valid
    # indented
\\# escaped
`````python
## ignored
```
### still ignored"""
        first = scan_text(Path("sample.md"), text)
        second = scan_text(Path("sample.md"), text)
        self.assertEqual(first, second)
        self.assertEqual([(item.heading, item.start_line, item.end_line) for item in first.sections], [("valid", 1, 7)])

    def test_setext_is_bounded_to_an_eligible_single_line_title(self) -> None:
        text = """Title
=====

Paragraph line one
Paragraph line two
-----

> quote
-----

Title two
-----"""
        fact = scan_text(Path("sample.md"), text)
        self.assertEqual([(item.heading, item.level, item.start_line) for item in fact.sections], [
            ("Title", 1, 1), ("Title two", 2, 11),
        ])

    def test_no_heading_unicode_crlf_and_final_line_without_newline(self) -> None:
        self.assertEqual(scan_text(Path("plain.md"), "α\r\nβ").physical_lines, 2)
        self.assertEqual(scan_text(Path("plain.md"), "α\r\nβ").sections, ())
        self.assertEqual(scan_text(Path("empty.md"), "").physical_lines, 0)

    def test_adjacent_and_repeated_headings_remain_distinct(self) -> None:
        fact = scan_text(Path("repeat.md"), "# Same\n## Empty\n# Same\n")
        self.assertEqual([(item.heading, item.start_line, item.end_line) for item in fact.sections], [
            ("Same", 1, 1), ("Empty", 2, 2), ("Same", 3, 3),
        ])

    def test_only_md_files_are_scanned_in_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "z.md").write_text("# Z\n", encoding="utf-8")
            (root / "a.md").write_text("# A\n", encoding="utf-8")
            (root / "ignored.markdown").write_text("# No\n", encoding="utf-8")
            facts = analyze_files((root / "z.md", root / "ignored.markdown", root / "a.md"))
            self.assertEqual([fact.path.name for fact in facts.documents], ["a.md", "z.md"])


class MarkdownGuardTests(unittest.TestCase):
    def _config(self, guard, value: object):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            path.write_text(json.dumps({"guards": {guard: value}}), encoding="utf-8")
            loader = markdown_document_size.load_config if guard == "markdownDocumentSize" else markdown_section_size.load_config
            return loader(args(path))

    def test_configuration_defaults_overrides_and_disable(self) -> None:
        for guard, default in (("markdownDocumentSize", 800), ("markdownSectionSize", 200)):
            loader = markdown_document_size.load_config if guard == "markdownDocumentSize" else markdown_section_size.load_config
            with self.subTest(guard=guard, value="omitted"):
                config = loader(args())
                self.assertEqual((config.enabled, config.review_at), (True, default))
            for value, expected in (({}, (True, default)), ({"enabled": True}, (True, default)),
                                    ({"reviewAt": 9}, (True, 9)), ({"enabled": True, "reviewAt": 10}, (True, 10)),
                                    ({"enabled": False}, (False, None)), ({"enabled": False, "reviewAt": "ignored"}, (False, None))):
                with self.subTest(guard=guard, value=value):
                    config = self._config(guard, value)
                    self.assertEqual((config.enabled, config.review_at), expected)

    def test_invalid_enabled_and_review_thresholds_are_rejected(self) -> None:
        for guard in ("markdownDocumentSize", "markdownSectionSize"):
            with self.assertRaisesRegex(ValueError, rf"guards.{guard}.enabled must be a boolean"):
                self._config(guard, {"enabled": 1})
            for value in (True, 1.5, "2", None, 0, -1):
                with self.subTest(guard=guard, value=value), self.assertRaisesRegex(
                    ValueError, rf"guards.{guard}.reviewAt must be a positive integer"
                ):
                    self._config(guard, {"reviewAt": value})

    def test_document_exact_threshold_passes_and_one_over_reviews_without_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exact = root / "exact.md"; write_lines(exact, 800)
            over = root / "over.md"; write_lines(over, 801)
            result = markdown_document_size.run(root, markdown_document_size.Config(True, 800), analyze_files((over, exact)))
            self.assertEqual(result.state, "review")
            self.assertEqual(result.required_policies, ["markdownDocumentSize"])
            self.assertEqual([(item.path, item.measured, item.state) for item in result.findings], [
                ("exact.md", 800, "pass"), ("over.md", 801, "review"),
            ])

    def test_section_emits_all_findings_in_path_and_start_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "repeat.md"
            path.write_text("# Same\n" + "x\n" * 200 + "# Same\n" + "y\n" * 200, encoding="utf-8")
            result = markdown_section_size.run(root, markdown_section_size.Config(True, 200), analyze_files((path,)))
            self.assertEqual(result.state, "review")
            self.assertEqual(result.required_policies, ["markdownSectionSize"])
            self.assertEqual([(item.heading, item.start_line, item.end_line, item.measured) for item in result.findings], [
                ("Same", 1, 201, 201), ("Same", 202, 402, 201),
            ])
            self.assertTrue(all(item.state == "review" for item in result.findings))


class MarkdownRunnerTests(CodeGuardTestCase):
    def test_default_guard_order_and_markdown_json_human_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / "large.md"
            path.write_text("# Huge\n" + "body\n" * 800, encoding="utf-8")
            result = self.run_guard(root, "large.md", "--json")
            data = self.read_json(result)
            self.assertEqual(list(data["guards"]), [
                "loc", "callableSize", "nesting", "complexity", "markdownDocumentSize", "markdownSectionSize",
            ])
            self.assertEqual(data["overall"], "review")
            self.assertEqual(data["requiredPolicies"], ["markdownDocumentSize", "markdownSectionSize"])
            document = data["guards"]["markdownDocumentSize"]["findings"][0]
            self.assertEqual(document, {
                "path": "large.md", "range": {"startLine": 1, "endLine": 801}, "measured": 801,
                "state": "review", "thresholds": {"reviewAt": 800},
            })
            section = data["guards"]["markdownSectionSize"]["findings"][0]
            self.assertEqual(section["heading"], "Huge")
            self.assertEqual(section["range"], {"startLine": 1, "endLine": 801})
            human = self.run_guard(root, "large.md")
            self.assertIn("large.md:1-801 — Markdown document is 801 lines (review 800)", human.stdout)
            self.assertIn('section "Huge" is 801 lines (review 200)', human.stdout)

    def test_markdown_scan_is_independently_lazy_and_shared_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); markdown = root / "notes.md"; markdown.write_text("# Notes\n", encoding="utf-8")
            source = root / "sample.py"; source.write_text("value = 1\n", encoding="utf-8")
            scope = ResolvedScope(root, (markdown, source))
            cases = [
                ({"markdownDocumentSize": {"enabled": False}, "markdownSectionSize": {"enabled": False}}, 0),
                ({"markdownSectionSize": {"enabled": False}}, 1),
                ({"markdownDocumentSize": {"enabled": False}}, 1),
                ({}, 1),
            ]
            for guards, expected in cases:
                config = write_config(root, {"enabled": False}, guards={
                    "callableSize": {"enabled": False}, "nesting": {"enabled": False},
                    "cyclomaticComplexity": {"enabled": False}, **guards,
                })
                with self.subTest(guards=guards), patch("agent_code_guard.markdown.analyze_files", wraps=analyze_files) as scan:
                    run_guards(scope, args(config))
                    self.assertEqual(scan.call_count, expected)

    def test_non_markdown_scope_does_not_call_scanner_and_markdown_does_not_call_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "sample.py"; source.write_text("value = 1\n", encoding="utf-8")
            markdown = root / "notes.md"; markdown.write_text("# Notes\n", encoding="utf-8")
            with patch("agent_code_guard.markdown.analyze_files", wraps=analyze_files) as scan:
                run_guards(ResolvedScope(root, (source,)), args())
                self.assertEqual(scan.call_count, 0)
            config = write_config(root, {"enabled": False}, guards={
                "callableSize": {"enabled": False}, "nesting": {"enabled": False},
                "cyclomaticComplexity": {"enabled": False},
            })
            with patch("agent_code_guard.analysis.pipeline.analyze_files") as syntax:
                run_guards(ResolvedScope(root, (markdown,)), args(config))
                syntax.assert_not_called()

    def test_global_scope_exclude_and_loc_exclude_remain_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / "docs" / "large.md"; write_lines(path, 801)
            loc_only = write_config(root, {"exclude": ["docs/**"]})
            result = self.run_guard(root, "docs/large.md", "--config", str(loc_only), "--json")
            self.assertEqual(len(self.read_json(result)["guards"]["markdownDocumentSize"]["findings"]), 1)
            global_config = write_config(root, {}, scope={"exclude": ["docs/**"]})
            result = self.run_guard(root, "docs/large.md", "--config", str(global_config), "--json")
            self.assertEqual(self.read_json(result)["guards"]["markdownDocumentSize"]["findings"], [])


if __name__ == "__main__":
    unittest.main()
