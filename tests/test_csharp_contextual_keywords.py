from __future__ import annotations

import tempfile
from pathlib import Path

from helpers import CodeGuardTestCase, REPO_ROOT, write_config


FIXTURE = REPO_ROOT / "tests" / "fixtures" / "csharp" / "ContextualKeywords.cs"


def assert_fixture_measurements(test: CodeGuardTestCase, payload: dict[str, object]) -> None:
    expected_ranges = {
        "Repro.Configure": {"startLine": 3, "endLine": 3},
        "Repro.Sync": {"startLine": 5, "endLine": 5},
        "Repro.Async": {"startLine": 7, "endLine": 7},
    }
    expected_measurements = {
        "callableSize": {identity: 1 for identity in expected_ranges},
        "nesting": {identity: 0 for identity in expected_ranges},
        "complexity": {"Repro.Configure": 2, "Repro.Sync": 1, "Repro.Async": 1},
    }
    for guard, measurements in expected_measurements.items():
        findings = {item["callable"]: item for item in payload["guards"][guard]["findings"]}
        test.assertEqual(set(findings), set(expected_ranges))
        test.assertEqual(
            {identity: item["measured"] for identity, item in findings.items()}, measurements,
        )
        test.assertEqual(
            {identity: item["range"] for identity, item in findings.items()}, expected_ranges,
        )


def write_source(root: Path, name: str, source: str) -> Path:
    path = root / name
    path.write_text(source, encoding="utf-8")
    return path


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
            assert_fixture_measurements(self, payload)

            genuine_async = write_source(
                root, "GenuineAsync.cs",
                "class Genuine { async System.Threading.Tasks.Task Run() { await Next(); } }\n",
            )
            genuine_result = self.run_guard(
                root, str(genuine_async), "--config", str(config), "--json",
            )
            self.assertNotEqual(genuine_result.returncode, 3, genuine_result.stderr)
            self.assertEqual(
                [item["callable"] for item in self.read_json(genuine_result)["guards"]["complexity"]["findings"]],
                ["Genuine.Run"],
            )

            expression_roles = write_source(
                root, "ExpressionRoles.cs",
                "class ExpressionRoles { "
                "bool Direct(bool async) => async; "
                "int Binary(int async) => async + 1; "
                "int Argument(int async) => Identity(async); "
                "string Member(string async) => async.ToString(); "
                "int Element(int[] async) => async[0]; "
                "string Cast(object async) => (string)async; "
                "int Identity(int value) => value; }\n",
            )
            expression_result = self.run_guard(
                root, str(expression_roles), "--config", str(config), "--json",
            )
            self.assertNotEqual(expression_result.returncode, 3, expression_result.stderr)
            self.assertEqual(
                {item["callable"] for item in self.read_json(expression_result)["guards"]["complexity"]["findings"]},
                {
                    "ExpressionRoles.Direct",
                    "ExpressionRoles.Binary",
                    "ExpressionRoles.Argument",
                    "ExpressionRoles.Member",
                    "ExpressionRoles.Element",
                    "ExpressionRoles.Cast",
                    "ExpressionRoles.Identity",
                },
            )

            unsupported_role = write_source(
                root, "UnsupportedRole.cs",
                "class UnsupportedRole { void Run() { async: return; } }\n",
            )
            unsupported_result = self.run_guard(root, str(unsupported_role), "--json")
            self.assert_syntax_unavailable(unsupported_result, "UnsupportedRole.cs")


if __name__ == "__main__":
    import unittest

    unittest.main()
