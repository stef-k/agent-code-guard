from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.markdown_guard_sample import _distribution, _section_finding_summary, measure, scan_text


class MarkdownScannerTests(unittest.TestCase):
    def test_atx_setext_and_section_ownership(self) -> None:
        result = scan_text(
            "preamble\n\n# A #\ntext A\n\n## B\ntext B\n\n## B\n\nC\n---\ntext C\n\n# D\n",
        )

        self.assertEqual(result["totalPhysicalLines"], 15)
        self.assertEqual(result["nonblankPhysicalLines"], 10)
        self.assertEqual(result["preambleLines"], 2)
        self.assertEqual(
            [(heading["text"], heading["level"], heading["startLine"], heading["endLine"])
             for heading in result["headings"]],
            [("A", 1, 3, 3), ("B", 2, 6, 6), ("B", 2, 9, 9),
             ("C", 2, 11, 12), ("D", 1, 15, 15)],
        )
        self.assertEqual(
            [(section["heading"], section["physicalLines"])
             for section in result["directContentSections"]],
            [("A", 3), ("B", 3), ("B", 2), ("C", 4), ("D", 1)],
        )
        self.assertEqual(
            [(section["heading"], section["physicalLines"])
             for section in result["subtreeSections"]],
            [("A", 12), ("B", 3), ("B", 2), ("C", 4), ("D", 1)],
        )

    def test_fenced_and_indented_code_do_not_create_headings(self) -> None:
        text = (
            "# Real\n"
            "````markdown\n# fenced\n```\n## still fenced\n````\n"
            "~~~~text\n## tilde\n~~~\n~~~~\n"
            "    # indented\n    Setext-looking\n    ----\n"
            "\\# escaped\n## Final ##\n"
        )

        result = scan_text(text)

        self.assertEqual(
            [(heading["text"], heading["level"]) for heading in result["headings"]],
            [("Real", 1), ("Final", 2)],
        )

    def test_preamble_no_heading_adjacent_empty_and_final_line(self) -> None:
        no_heading = scan_text("alpha\r\nβeta")
        adjacent = scan_text("# One\n## Two")

        self.assertEqual(no_heading["totalPhysicalLines"], 2)
        self.assertEqual(no_heading["nonblankPhysicalLines"], 2)
        self.assertEqual(no_heading["preambleLines"], 2)
        self.assertEqual(no_heading["headings"], [])
        self.assertEqual(no_heading["directContentSections"], [])
        self.assertEqual(adjacent["directContentSections"][0]["physicalLines"], 1)
        self.assertEqual(adjacent["subtreeSections"][0]["physicalLines"], 2)

    def test_unclosed_fence_treats_remainder_as_fenced_content(self) -> None:
        result = scan_text("# Real\n```\n## hidden\n")

        self.assertEqual(len(result["headings"]), 1)
        self.assertEqual(result["unclosedFence"], True)

    def test_atx_boundaries_and_setext_eligibility_are_bounded(self) -> None:
        result = scan_text(
            "   ###### Six ######\n"
            "    # indented\n"
            "####### seven\n"
            "#missing-space\n"
            "\n"
            "Title\n=======\n"
            "\nNot a title\n\n---\n",
        )

        self.assertEqual(
            [(heading["text"], heading["level"]) for heading in result["headings"]],
            [("Six", 6), ("Title", 1)],
        )

    def test_backtick_info_with_backtick_is_not_a_fence(self) -> None:
        result = scan_text("```bad`info\n# visible\n")

        self.assertEqual(result["headings"][0]["text"], "visible")
        self.assertFalse(result["unclosedFence"])

    def test_setext_does_not_promote_other_block_constructs(self) -> None:
        result = scan_text(
            "- item\n---\n\n> quote\n---\n\n<div>\n---\n\n1. item\n---\n\nFoo\nBar\n---\n",
        )

        self.assertEqual(result["headings"], [])

    def test_line_endings_unicode_and_fence_measurement_are_deterministic(self) -> None:
        lf = scan_text("# Καλημέρα\n~~~\n## hidden\n~~\n```\n~~~\n")
        crlf = scan_text("# Καλημέρα\r\n~~~\r\n## hidden\r\n~~\r\n```\r\n~~~\r\n")

        self.assertEqual(lf, crlf)
        self.assertEqual(lf["headings"][0]["text"], "Καλημέρα")
        self.assertEqual(lf["directContentSections"][0]["physicalLines"], 6)
        self.assertEqual(lf["directContentSections"][0]["physicalLinesExcludingFencedCode"], 1)


class MarkdownMeasurementTests(unittest.TestCase):
    def test_measurement_orders_markdown_paths_and_summarizes_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z.markdown").write_text("# Z\nbody", encoding="utf-8")
            (root / "a.md").write_text("# A\n\nbody\n", encoding="utf-8")
            (root / "ignored.txt").write_text("# Not Markdown\n", encoding="utf-8")

            result = measure([str(root)], root, document_thresholds=(2,), section_thresholds=(1,))

        self.assertEqual([row["path"] for row in result["documents"]], ["a.md", "z.markdown"])
        self.assertEqual(result["summary"]["documents"], 2)
        self.assertEqual(result["summary"]["totalPhysicalLines"]["median"], 2.5)
        self.assertEqual(result["summary"]["totalPhysicalLines"]["above"]["2"]["count"], 1)
        self.assertEqual(result["summary"]["maxDirectContentSectionLines"]["above"]["1"]["count"], 2)
        finding_summary = result["summary"]["directContentSectionFindings"]
        self.assertEqual(finding_summary["totalSections"], 2)
        self.assertEqual(
            finding_summary["above"]["1"],
            {
                "findingCount": 2,
                "findingPercent": 100.0,
                "affectedDocuments": 2,
                "affectedDocumentPercent": 100.0,
                "documentsWithMultipleFindings": 0,
                "findingsPerDocument": {"1": 2},
            },
        )

    def test_measurement_exclusions_are_root_relative_globs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "keep.md").write_text("# Keep\n", encoding="utf-8")
            generated = root / "generated"
            generated.mkdir()
            (generated / "skip.md").write_text("# Skip\n", encoding="utf-8")

            result = measure([str(root)], root, excludes=("generated/**",))

        self.assertEqual([row["path"] for row in result["documents"]], ["keep.md"])

    def test_duplicate_inputs_and_empty_distribution_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "same.md"
            source.write_text("# Same\n", encoding="utf-8")

            result = measure([str(source), str(root), str(source)], root)

        self.assertEqual([row["path"] for row in result["documents"]], ["same.md"])
        self.assertEqual(_distribution([], (100,))["median"], None)
        self.assertEqual(_distribution([1, 2, 3, 4], (2,))["p99"], 4)
        self.assertEqual(_distribution([1, 2, 3, 4], (2,))["above"]["2"]["count"], 2)

    def test_selected_thresholds_pass_at_exact_value_and_review_above(self) -> None:
        documents = _distribution([800, 801], (800,))
        sections = _distribution([200, 201], (200,))

        self.assertEqual(documents["above"]["800"]["count"], 1)
        self.assertEqual(sections["above"]["200"]["count"], 1)

    def test_repeat_measurement_serializes_identically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "stable.md").write_text("# Stable\nbody\n", encoding="utf-8")

            first = json.dumps(measure([str(root)], root), sort_keys=True, ensure_ascii=False)
            second = json.dumps(measure([str(root)], root), sort_keys=True, ensure_ascii=False)

        self.assertEqual(first, second)

    def test_section_finding_summary_counts_multiple_findings_per_document(self) -> None:
        documents = [
            {"directContentSections": [{"physicalLines": 3}, {"physicalLines": 2}]},
            {"directContentSections": [{"physicalLines": 1}]},
        ]

        summary = _section_finding_summary(documents, (1, 2))

        self.assertEqual(summary["totalSections"], 3)
        self.assertEqual(
            summary["above"]["1"],
            {
                "findingCount": 2,
                "findingPercent": 66.67,
                "affectedDocuments": 1,
                "affectedDocumentPercent": 50.0,
                "documentsWithMultipleFindings": 1,
                "findingsPerDocument": {"0": 1, "2": 1},
            },
        )
        self.assertEqual(summary["above"]["2"]["findingCount"], 1)
        self.assertEqual(summary["above"]["2"]["findingsPerDocument"], {"0": 1, "1": 1})


if __name__ == "__main__":
    unittest.main()
