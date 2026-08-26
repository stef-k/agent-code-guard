from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import CodeGuardTestCase


class CompletedAnalysisOutputTests(CodeGuardTestCase):
    def test_formats_one_complete_mixed_report_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text(
                "def sample(value):\n    if value:\n        if value > 1:\n"
                "            return value\n    return 0\n",
                encoding="utf-8",
            )
            (root / "guide.md").write_text('# Hé said `"hello`"\nbody\nbody\n', encoding="utf-8")
            config = root / "code-guard.config.json"
            config.write_text(json.dumps({"version": 1, "guards": {
                "loc": {"warnAt": 1, "failAt": 99},
                "callableSize": {"reviewAt": 3},
                "nesting": {"reviewAt": 1},
                "cyclomaticComplexity": {"reviewAt": 1},
                "markdownDocumentSize": {"reviewAt": 2},
                "markdownSectionSize": {"reviewAt": 2},
            }}), encoding="utf-8")

            result = self.run_guard(root, ".", "--config", str(config))

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")
            self.assertEqual(result.stdout, "\n".join([
                "REVIEW: 3 selected; 2 analyzed; 1 inapplicable; 0 excluded.",
                "REVIEW: sample.py — 5 LOC (warn 1, fail 99)",
                "REVIEW: sample.py:1-5 — sample.sample is 5 LOC (review 3)",
                "REVIEW: sample.py:1-5 — sample.sample nesting depth 2 (review 1; deepest at line 3)",
                "REVIEW: sample.py:1-5 — sample.sample complexity 3 (review 1)",
                "REVIEW: guide.md — Markdown document is 3 lines (review 2)",
                'REVIEW: guide.md:1-3 — section "Hé said `\\"hello`\\"" is 3 lines (review 2)',
                "Required policies: callableSize, complexity, loc, markdownDocumentSize, markdownSectionSize, nesting",
                "Required action: inspect each actionable finding using its policy guidance.",
                "",
            ]))


if __name__ == "__main__":
    import unittest
    unittest.main()
