from __future__ import annotations

import tempfile
from pathlib import Path

from helpers import CodeGuardTestCase, REPO_ROOT, write_config


FIXTURE = REPO_ROOT / "tests" / "fixtures" / "analyzers" / "csharp" / "ContextualKeywords.cs"


class CSharpContextualKeywordPublicTests(CodeGuardTestCase):
    def test_async_identifiers_and_named_arguments_preserve_callable_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = write_config(root, {"enabled": False}, guards={
                "callableSize": {"reviewAt": 1},
                "nesting": {"reviewAt": 1},
                "cyclomaticComplexity": {"reviewAt": 1},
                "markdownDocumentSize": {"enabled": False},
                "markdownSectionSize": {"enabled": False},
            })

            result = self.run_guard(root, str(FIXTURE), "--config", str(config), "--json")

            self.assertNotEqual(result.returncode, 3, result.stderr)
            payload = self.read_json(result)
            expected_ranges = {
                "Repro.Configure": {"startLine": 3, "endLine": 3},
                "Repro.Sync": {"startLine": 5, "endLine": 5},
                "Repro.Async": {"startLine": 7, "endLine": 7},
            }
            expected_measurements = {
                "callableSize": {identity: 1 for identity in expected_ranges},
                "nesting": {identity: 0 for identity in expected_ranges},
                "complexity": {
                    "Repro.Configure": 2,
                    "Repro.Sync": 1,
                    "Repro.Async": 1,
                },
            }
            for guard, measurements in expected_measurements.items():
                findings = {item["callable"]: item for item in payload["guards"][guard]["findings"]}
                self.assertEqual(set(findings), set(expected_ranges))
                self.assertEqual(
                    {identity: item["measured"] for identity, item in findings.items()},
                    measurements,
                )
                self.assertEqual(
                    {identity: item["range"] for identity, item in findings.items()},
                    expected_ranges,
                )


if __name__ == "__main__":
    import unittest

    unittest.main()
