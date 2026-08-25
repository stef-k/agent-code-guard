from __future__ import annotations

import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from tests.test_cli_version import checkout_code_guard as code_guard

CompletedAnalysis = code_guard.CompletedAnalysis
ScopeSummary = code_guard.ScopeSummary
CallableFinding = code_guard.callable_size.CallableFinding
Finding = code_guard.loc.Finding
GuardResult = code_guard.GuardResult


class JsonModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = CompletedAnalysis(
            [
                GuardResult(
                    "loc",
                    "pass",
                    [Finding("allowed.py", "pass", "exempt", 120, 100, 200, 0, "approved")],
                ),
                GuardResult(
                    "callableSize",
                    "review",
                    [
                        CallableFinding("mixed.py", "small", 1, 2, 2, "pass", {"reviewAt": 3}),
                        CallableFinding("mixed.py", "reviewed", 4, 8, 5, "review", {"reviewAt": 3}),
                        CallableFinding("mixed.py", "failed", 10, 20, 11, "fail", {"reviewAt": 3}),
                    ],
                ),
            ],
            ScopeSummary(3, 2, 1, 0),
        )

    def run_main(self, *arguments: str) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.object(sys, "argv", ["code-guard", *arguments]),
            patch.object(code_guard, "validate_configuration"),
            patch.object(code_guard, "resolve_scope", return_value=object()),
            patch.object(code_guard, "run_analysis", return_value=self.analysis),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = code_guard.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_compact_filters_only_passing_findings_from_a_mixed_result(self) -> None:
        full = code_guard.payload(self.analysis)
        compact = code_guard.payload(self.analysis, "compact")

        self.assertEqual(compact["overall"], full["overall"])
        self.assertEqual(compact["scope"], full["scope"])
        self.assertEqual(compact["requiredPolicies"], full["requiredPolicies"])
        self.assertEqual(list(compact["guards"]), list(full["guards"]))
        self.assertEqual(
            {guard: value["state"] for guard, value in compact["guards"].items()},
            {guard: value["state"] for guard, value in full["guards"].items()},
        )
        self.assertEqual(compact["guards"]["loc"]["findings"], [])
        self.assertEqual(
            compact["guards"]["callableSize"]["findings"],
            full["guards"]["callableSize"]["findings"][1:],
        )

    def test_bare_and_debug_completed_json_are_byte_identical(self) -> None:
        bare = self.run_main("--json")
        debug = self.run_main("--json", "--json-mode", "debug")

        self.assertEqual(debug, bare)
        self.assertEqual(bare[0], 1)
        self.assertEqual(bare[2], "")

    def test_analysis_mode_cli_compatibility(self) -> None:
        cases = (
            ("compact_without_json", ("--json-mode", "compact"), False),
            ("debug_without_json", ("--json-mode", "debug"), False),
            ("version_compact", ("--version", "--json", "--json-mode", "compact"), True),
            ("version_debug", ("--version", "--json", "--json-mode", "debug"), True),
        )
        for name, arguments, json_error in cases:
            with self.subTest(name=name):
                code, stdout, stderr = self.run_main(*arguments)
                self.assertEqual(code, 3)
                if json_error:
                    self.assertEqual(stderr, "")
                    self.assertEqual(set(json.loads(stdout)), {"error"})
                    self.assertNotIn("distribution", stdout)
                else:
                    self.assertEqual(stdout, "")
                    self.assertTrue(stderr.startswith("Code Guard error: "))


if __name__ == "__main__":
    unittest.main()
