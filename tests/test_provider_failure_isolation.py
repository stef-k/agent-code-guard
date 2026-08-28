from __future__ import annotations

import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase, write_config


class ProviderFailureIsolationLifecycleTests(CodeGuardTestCase):
    def test_mixed_public_run_preserves_independent_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            valid = root / "valid.py"
            broken = root / "broken.py"
            markdown = root / "guide.md"
            valid.write_text(
                "def classify(value):\n"
                "    if value:\n"
                "        return 1\n"
                "    return 0\n",
                encoding="utf-8",
            )
            broken.write_text("def broken(:\n", encoding="utf-8")
            markdown.write_text("# Guide\n\nUseful text.\n", encoding="utf-8")
            config = write_config(root, {"warnAt": 3, "failAt": 20})

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
            self.assertEqual(data["requiredPolicies"], ["loc"])
            self.assertEqual(data["guards"]["loc"]["complete"], True)
            for guard_id in ("callableSize", "nesting", "complexity"):
                self.assertEqual(data["guards"][guard_id]["complete"], False)
                self.assertEqual(data["guards"][guard_id]["unavailablePaths"], ["broken.py"])
            for guard_id in ("markdownDocumentSize", "markdownSectionSize"):
                self.assertEqual(data["guards"][guard_id]["complete"], True)
            self.assertTrue(any(item["path"] == "valid.py" for item in data["guards"]["loc"]["findings"]))
            self.assertTrue(data["guards"]["complexity"]["findings"])


if __name__ == "__main__":
    import unittest

    unittest.main()
