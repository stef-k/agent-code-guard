from __future__ import annotations

import unittest

from research.style_guard_sample import scan_bytes, summarize


class StyleGuardSampleTests(unittest.TestCase):
    def test_css_ranges_ignore_braces_in_comments_strings_and_interpolation(self) -> None:
        source = """/* { } */
.card, .panel {
  content: "}";
  color: red;
}
""".encode()

        result = scan_bytes(source, "css")

        self.assertEqual(result["physicalLines"], 5)
        self.assertEqual(len(result["blocks"]), 1)
        self.assertEqual(result["blocks"][0]["physical_lines"], 4)
        self.assertEqual(result["blocks"][0]["declarations"], 2)
        self.assertEqual(result["selectors"][0]["selector_count"], 2)

    def test_scss_distinguishes_selector_at_rule_and_control_depth(self) -> None:
        source = """.card {
  &__title {
    @media (width > 10rem) {
      &:hover { color: #{$accent}; }
    }
  }
}
@mixin themed($dark) {
  @if $dark { color: black; }
}
@function doubled($value) { @return $value * 2; }
""".encode()

        result = scan_bytes(source, "scss")

        rules = [block for block in result["blocks"] if block["kind"] == "rule"]
        self.assertEqual([rule["selector_depth"] for rule in rules], [1, 2, 3])
        self.assertEqual([rule["has_parent_selector"] for rule in rules], [False, True, True])
        media = next(block for block in result["blocks"] if block["kind"] == "at-rule")
        self.assertEqual(media["at_rule_depth"], 1)
        control = next(block for block in result["blocks"] if block["kind"] == "control")
        self.assertEqual(control["control_depth"], 1)
        self.assertEqual(
            {block["kind"] for block in result["blocks"]},
            {"rule", "at-rule", "mixin", "function", "control"},
        )

    def test_keyframes_steps_are_not_selectors(self) -> None:
        result = scan_bytes(
            b"@keyframes pulse {\n from { opacity: 0; }\n 50% { opacity: .5; }\n to { opacity: 1; }\n}",
            "css",
        )

        self.assertEqual(
            [block["kind"] for block in result["blocks"]],
            ["keyframes", "keyframe-step", "keyframe-step", "keyframe-step"],
        )
        self.assertEqual(result["selectors"], [])

    def test_lf_crlf_unicode_and_empty_blocks_are_deterministic(self) -> None:
        lf = scan_bytes(".λ {\n}\n.empty {}\n".encode(), "scss")
        crlf = scan_bytes(".λ {\r\n}\r\n.empty {}\r\n".encode(), "scss")

        self.assertEqual(lf, crlf)
        self.assertEqual([block["physical_lines"] for block in lf["blocks"]], [2, 1])
        self.assertEqual([block["declarations"] for block in lf["blocks"]], [0, 0])

    def test_malformed_input_recovers_to_eof_with_telemetry(self) -> None:
        result = scan_bytes(b".a { color: red; .b { content: '}'; }", "scss")

        self.assertTrue(result["parseHasError"])
        self.assertEqual(result["recoveredBlocks"], 1)
        self.assertEqual(result["blocks"][0]["end_line"], 1)
        self.assertTrue(result["blocks"][0]["recovered"])

    def test_summary_reports_actual_and_document_finding_rates(self) -> None:
        first = scan_bytes(b".a {\n x: 1;\n y: 2;\n}\n.b {\n x: 1;\n y: 2;\n}", "css")
        second = scan_bytes(b".a { x: 1; }", "css")

        summary = summarize(
            [first, second],
            {"blockSize": [3], "selectorDepth": [1], "selectorComponents": [1], "declarations": [1]},
        )

        row = summary["blockSizeFindings"]["above"]["3"]
        self.assertEqual(row["findingCount"], 2)
        self.assertEqual(row["affectedDocuments"], 1)
        self.assertEqual(row["documentsWithMultipleFindings"], 1)


if __name__ == "__main__":
    unittest.main()
