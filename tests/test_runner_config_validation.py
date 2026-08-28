from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase, write_config, write_lines


class ConfigurationValidationTests(CodeGuardTestCase):
    def test_ratchet_at_accepts_only_exact_policy_strings_and_defaults_to_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "sample.py", 4)
            for value in ("FAIL", "Review", "other", True, 1, None):
                with self.subTest(value=value):
                    config = write_config(root, {"warnAt": 3, "failAt": 6, "ratchetAt": value})
                    result = self.run_guard(root, ".", "--config", str(config), "--json")
                    self.assertEqual(result.returncode, 3)
                    self.assertIn("guards.loc.ratchetAt must be 'fail' or 'review'", self.read_json(result)["error"])
            for value in ("fail", "review"):
                config = write_config(root, {"warnAt": 3, "failAt": 6, "ratchetAt": value})
                self.assertEqual(self.run_guard(root, ".", "--config", str(config), "--json").returncode, 1)

    def test_global_thresholds_require_positive_json_integers(self) -> None:
        invalid_values = ["3", True, 3.0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for field in ["warnAt", "failAt"]:
                for value in invalid_values:
                    with self.subTest(field=field, value=value):
                        loc = {"warnAt": 3, "failAt": 6, field: value}
                        config = write_config(root, loc)
                        result = self.run_guard(root, ".", "--config", str(config), "--json")
                        self.assertEqual(result.returncode, 3)
                        self.assertIn(f"guards.loc.{field} must be a positive integer", self.read_json(result)["error"])

    def test_positive_integer_global_thresholds_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "sample.py", 4)
            config = write_config(root, {"warnAt": 3, "failAt": 6})
            result = self.run_guard(root, ".", "--config", str(config), "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(self.findings(result)[0]["nativeStatus"], "warn")

    def test_malformed_exemptions_are_errors(self) -> None:
        entries = [None, {}, {"path": ""}, {"path": "x.py", "reason": ""}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for entry in entries:
                with self.subTest(entry=entry):
                    config = write_config(root, {"allowedLargeFiles": [entry]})
                    self.assertEqual(self.run_guard(root, ".", "--config", str(config), "--json").returncode, 3)

    def test_malformed_overrides_are_errors(self) -> None:
        entries = [{}, {"match": [], "warnAt": 3, "failAt": 6}, {"match": ["*.py"], "warnAt": True, "failAt": 6}, {"match": ["*.py"], "warnAt": 6, "failAt": 6}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for entry in entries:
                with self.subTest(entry=entry):
                    config = write_config(root, {"overrides": [entry]})
                    self.assertEqual(self.run_guard(root, ".", "--config", str(config), "--json").returncode, 3)

    def test_malformed_top_level_structures_are_errors(self) -> None:
        documents = [[], {"guards": []}, {"guards": {"loc": []}}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, document in enumerate(documents):
                path = root / f"bad-{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                self.assertEqual(self.run_guard(root, ".", "--config", str(path), "--json").returncode, 3)
