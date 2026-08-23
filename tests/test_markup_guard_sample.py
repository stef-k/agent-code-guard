from __future__ import annotations

import unittest

from research.markup_guard_sample import MarkupMeasurementError, scan_bytes, summarize


class MarkupGuardSampleTests(unittest.TestCase):
    def test_html_measurement_handles_void_raw_text_unicode_and_recovery(self) -> None:
        source = """<!doctype html>\r\n<html><body>λ<br><script>if (a < b) { x++; }</script>\r\n<div><span></div></body></html>""".encode()

        result = scan_bytes(source, "html")

        self.assertEqual(
            [element["tag"] for element in result["elements"]],
            ["html", "body", "br", "script", "div", "span"],
        )
        self.assertEqual(
            result["elements"][0],
            {
                "tag": "html",
                "depth": 1,
                "start_line": 2,
                "end_line": 3,
                "physical_lines": 2,
                "direct_children": 1,
                "is_root": True,
            },
        )
        self.assertEqual(result["elements"][1]["direct_children"], 3)
        self.assertFalse(result["parseHasError"])
        self.assertEqual(result["errorOrMissingNodes"], 1)

    def test_xml_measurement_handles_namespace_declaration_cdata_comment_and_empty_element(
        self,
    ) -> None:
        source = b"""<?xml version="1.0"?>\n<!DOCTYPE root>\n<root xmlns:x="urn:x">\n<!-- note --><x:item><![CDATA[a < b]]></x:item><empty/>\n</root>"""

        result = scan_bytes(source, "xml")

        self.assertEqual(
            [(e["tag"], e["depth"], e["direct_children"]) for e in result["elements"]],
            [("root", 1, 2), ("x:item", 2, 0), ("empty", 2, 0)],
        )
        self.assertEqual(result["elements"][0]["physical_lines"], 3)

    def test_malformed_xml_is_a_measurement_error(self) -> None:
        with self.assertRaisesRegex(MarkupMeasurementError, "syntax error"):
            scan_bytes(b"<root><item></root>", "xml")

    def test_lf_and_crlf_produce_the_same_physical_ranges(self) -> None:
        lf = scan_bytes(b"<root>\n<item/>\n</root>\n", "xml")
        crlf = scan_bytes(b"<root>\r\n<item/>\r\n</root>\r\n", "xml")

        self.assertEqual(lf["physicalLines"], 3)
        self.assertEqual(crlf["physicalLines"], 3)
        self.assertEqual(lf["elements"], crlf["elements"])

    def test_summary_reports_actual_findings_and_multi_finding_documents(self) -> None:
        first = scan_bytes(b"<a>\n<b><c/></b>\n<d><e/></d>\n</a>", "xml")
        second = scan_bytes(b"<a><b/></a>", "xml")

        summary = summarize(
            [first, second], {"depth": [2], "subtreeSpan": [1], "fanOut": [1]}
        )

        self.assertEqual(summary["depthFindings"]["above"]["2"]["findingCount"], 2)
        self.assertEqual(
            summary["depthFindings"]["above"]["2"]["documentsWithMultipleFindings"], 1
        )
        self.assertEqual(
            summary["subtreeSpanFindings"]["above"]["1"]["findingCount"], 0
        )
        self.assertEqual(summary["fanOutFindings"]["above"]["1"]["findingCount"], 1)
