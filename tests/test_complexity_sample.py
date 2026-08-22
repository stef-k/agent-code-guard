from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from research.complexity_sample import _nearest_rank, measure


class ComplexitySampleTests(unittest.TestCase):
    def test_measurement_uses_production_callable_and_decision_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.py"
            source.write_text(
                "def choose(left, right):\n"
                "    if left and right:\n"
                "        return left\n"
                "    return right\n",
                encoding="utf-8",
            )

            result = measure([str(source)], root)

        self.assertEqual(result["supportedFiles"], 1)
        self.assertEqual(result["summary"]["python"]["callables"], 1)
        self.assertEqual(result["callables"][0]["complexity"], 3)
        self.assertEqual(
            result["callables"][0]["decisions"],
            {"condition": 1, "short_circuit_boolean": 1},
        )

    def test_nearest_rank_is_deterministic_for_small_samples(self) -> None:
        values = [1, 2, 3, 4]
        self.assertEqual(_nearest_rank(values, 0.75), 3)
        self.assertEqual(_nearest_rank(values, 0.95), 4)


if __name__ == "__main__":
    unittest.main()
