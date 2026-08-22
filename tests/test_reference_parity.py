"""Representative expectations captured from Agent LOC Guard 75ab39d."""

from __future__ import annotations

import tempfile
from pathlib import Path

from helpers import CodeGuardTestCase, write_config, write_lines


class StableReferenceParityTests(CodeGuardTestCase):
    CASES = [(3, "ok", 0), (4, "warn", 1), (6, "warn", 1), (7, "fail", 2)]

    def test_threshold_boundary_table_matches_stable_reference(self) -> None:
        for lines, expected, exit_code in self.CASES:
            with self.subTest(lines=lines), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); write_lines(root / "sample.py", lines)
                result = self.run_guard(root, ".", "--warn", "3", "--fail", "6", "--json")
                self.assertEqual((self.findings(result)[0]["nativeStatus"], result.returncode), (expected, exit_code))

    def test_literal_path_precedes_glob_interpretation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); write_lines(root / "file[1].py", 7)
            config = write_config(root, {"warnAt": 3, "failAt": 6, "allowedLargeFiles": [{"path": "file[1].py", "reason": "Reference parity."}]})
            result = self.run_guard(root, ".", "--config", str(config), "--json")
            self.assertEqual(self.findings(result)[0]["nativeStatus"], "exempt")
