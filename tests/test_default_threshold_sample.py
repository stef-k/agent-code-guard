from __future__ import annotations

import unittest
from pathlib import Path

from agent_code_guard.analysis.facts import (
    AnalysisFacts,
    CallableFact,
    CallableKey,
    ControlFlowFact,
    DecisionFact,
    SourceRange,
)
from research.default_threshold_sample import summarize


class DefaultThresholdSampleTests(unittest.TestCase):
    def test_summarizes_all_metrics_and_strict_candidate_rates(self) -> None:
        path = Path("sample.py")
        first_key = CallableKey(path, 0, 100)
        second_key = CallableKey(path, 101, 180)
        first_range = SourceRange(1, 10, 0, 100)
        second_range = SourceRange(11, 18, 101, 180)
        outer = SourceRange(2, 9, 10, 90)
        inner = SourceRange(3, 8, 20, 80)
        facts = AnalysisFacts(
            files=(path,),
            callables=(
                CallableFact(first_key, path, "python", "large", first_range, "declaration"),
                CallableFact(second_key, path, "python", "small", second_range, "declaration"),
            ),
            controls=(
                ControlFlowFact(first_key, outer, "condition", None),
                ControlFlowFact(first_key, inner, "loop", outer),
            ),
            decisions=(
                DecisionFact(first_key, SourceRange(2, 2, 10, 20), "condition"),
                DecisionFact(first_key, SourceRange(3, 3, 20, 30), "loop"),
            ),
        )

        result = summarize(facts, Path.cwd(), {"callableSize": (8,), "nesting": (1,), "complexity": (2,)})

        summary = result["summary"]["python"]
        self.assertEqual(summary["callableSize"]["values"], {"median": 9.0, "p75": 10, "p90": 10, "p95": 10, "p99": 10, "max": 10})
        self.assertEqual(summary["nesting"]["candidates"]["1"], {"count": 1, "percent": 50.0})
        self.assertEqual(summary["complexity"]["candidates"]["2"], {"count": 1, "percent": 50.0})
        self.assertEqual(result["callables"][0]["nesting"], 2)
        self.assertEqual(result["callables"][0]["complexity"], 3)


if __name__ == "__main__":
    unittest.main()
