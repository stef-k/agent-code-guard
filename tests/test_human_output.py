from __future__ import annotations

import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agent_code_guard.human_output import format_completed_analysis


class CompletedAnalysisOutputTests(unittest.TestCase):
    def test_formats_one_complete_mixed_report_exactly(self) -> None:
        data = {
            "overall": "review",
            "scope": {"selected": 3, "analyzed": 3, "inapplicable": 0, "excluded": 0},
            "guards": {
                "loc": {"findings": [{
                    "path": "large.py", "countedLoc": 450, "warnAt": 400, "failAt": 600,
                    "state": "review", "nativeStatus": "grandfathered", "baselineLoc": 460,
                    "ratchetStatus": "within", "overrideIndex": 2, "reason": "Generated boundary",
                }]},
                "callableSize": {"findings": [{
                    "path": "large.py", "range": {"startLine": 10, "endLine": 95},
                    "callable": "large.run", "measured": 86, "state": "review",
                    "thresholds": {"reviewAt": 80},
                }]},
                "nesting": {"findings": [{
                    "path": "nested.py", "range": {"startLine": 3, "endLine": 20},
                    "callable": "nested.walk", "measured": 5, "state": "review",
                    "thresholds": {"reviewAt": 4}, "details": {"deepestLine": 12},
                }]},
                "complexity": {"findings": [{
                    "path": "large.py", "range": {"startLine": 10, "endLine": 95},
                    "callable": "large.run", "measured": 16, "state": "review",
                    "thresholds": {"reviewAt": 15},
                }]},
                "markdownDocumentSize": {"findings": [{
                    "path": "guide.md", "measured": 801, "state": "review",
                    "thresholds": {"reviewAt": 800},
                }]},
                "markdownSectionSize": {"findings": [{
                    "path": "guide.md", "range": {"startLine": 2, "endLine": 205},
                    "heading": "Hé said \"hello\"", "measured": 204, "state": "review",
                    "thresholds": {"reviewAt": 200},
                }]},
            },
            "requiredPolicies": ["loc", "callableSize", "nesting", "complexity", "markdownDocumentSize"],
        }

        self.assertEqual(format_completed_analysis(data), "\n".join([
            "REVIEW: 3 selected; 3 analyzed; 0 inapplicable; 0 excluded.",
            "RATCHET: large.py — 450 LOC (warn 400, fail 600; baseline 460, within)",
            "  Threshold override: 2", "  Reason: Generated boundary",
            "REVIEW: large.py:10-95 — large.run is 86 LOC (review 80)",
            "REVIEW: nested.py:3-20 — nested.walk nesting depth 5 (review 4; deepest at line 12)",
            "REVIEW: large.py:10-95 — large.run complexity 16 (review 15)",
            "REVIEW: guide.md — Markdown document is 801 lines (review 800)",
            'REVIEW: guide.md:2-205 — section "Hé said \\"hello\\"" is 204 lines (review 200)',
            "Required policies: loc, callableSize, nesting, complexity, markdownDocumentSize",
            "Required action: inspect each actionable finding using its policy guidance.",
        ]))


if __name__ == "__main__":
    unittest.main()
