from __future__ import annotations

import unittest
from argparse import ArgumentTypeError
from pathlib import Path

from agent_code_guard.analysis.facts import (
    AnalysisFacts,
    CallableFact,
    CallableKey,
    ControlFlowFact,
    DecisionFact,
    FileFacts,
    SourcePoint,
    SourceRange,
)
from research.default_threshold_sample import _candidate, summarize


class DefaultThresholdSampleTests(unittest.TestCase):
    def test_candidate_parser_requires_known_metric_and_positive_integer(self) -> None:
        self.assertEqual(_candidate("complexity=15"), ("complexity", 15))
        for value in ("unknown=15", "complexity", "complexity=true", "complexity=0", "complexity=-1"):
            with self.subTest(value=value), self.assertRaises(ArgumentTypeError):
                _candidate(value)

    def test_summarizes_all_metrics_and_strict_candidate_rates(self) -> None:
        path = Path("sample.py")
        def source_range(start_line: int, end_line: int, start: int, end: int) -> SourceRange:
            return SourceRange(SourcePoint(start_line, 1, start), SourcePoint(end_line + 1, 1, end))

        first_range = source_range(1, 10, 0, 100)
        second_range = source_range(11, 18, 101, 180)
        first_key = CallableKey(path, "python", "large", first_range)
        second_key = CallableKey(path, "python", "small", second_range)
        first = CallableFact(path, "python", "large", first_range, None, "declaration", first_key, None)
        second = CallableFact(path, "python", "small", second_range, None, "declaration", second_key, None)
        outer = source_range(2, 9, 10, 90)
        inner = source_range(3, 8, 20, 80)
        controls = (
            ControlFlowFact("large", first_key, "condition", "if", outer, None),
            ControlFlowFact("large", first_key, "loop", "for", inner, outer),
        )
        decisions = (
            DecisionFact("large", first_key, "condition", "if", source_range(2, 2, 10, 20)),
            DecisionFact("large", first_key, "loop", "for", source_range(3, 3, 20, 30)),
        )
        facts = AnalysisFacts((FileFacts(path, (first, second), controls, decisions, 1),))

        result = summarize(facts, Path.cwd(), {"callableSize": (8,), "nesting": (1,), "complexity": (2,)})

        summary = result["summary"]["python"]
        self.assertEqual(summary["callableSize"]["values"], {"median": 9.0, "p75": 10, "p90": 10, "p95": 10, "p99": 10, "max": 10})
        self.assertEqual(summary["nesting"]["candidates"]["1"], {"count": 1, "percent": 50.0})
        self.assertEqual(summary["complexity"]["candidates"]["2"], {"count": 1, "percent": 50.0})
        self.assertEqual(result["callables"][0]["nesting"], 2)
        self.assertEqual(result["callables"][0]["complexity"], 3)


if __name__ == "__main__":
    unittest.main()
