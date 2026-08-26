from __future__ import annotations

import tempfile
from pathlib import Path

from tests.helpers import CodeGuardTestCase, write_config, write_lines


class ResultContractTests(CodeGuardTestCase):
    def test_zero_config_json_contains_all_default_guards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text("def sample():\n    return 1\n", encoding="utf-8")
            result = self.run_guard(root, ".", "--json")
            self.assertEqual((result.returncode, list(self.read_json(result)["guards"])), (0, [
                "loc", "callableSize", "nesting", "complexity", "markdownDocumentSize", "markdownSectionSize",
            ]))

    def test_pass_review_fail_and_policy_routing(self) -> None:
        cases = [(2, "pass", "ok", 0, []), (4, "review", "warn", 1, ["loc"]), (7, "fail", "fail", 2, ["loc"])]
        for lines, overall, native, code, policies in cases:
            with self.subTest(overall=overall), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                write_lines(root / "sample.py", lines)
                result = self.run_guard(root, ".", "--warn", "3", "--fail", "6", "--json")
                data = self.read_json(result)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(data["overall"], overall)
                self.assertEqual(data["requiredPolicies"], policies)
                self.assertEqual(data["guards"]["loc"]["findings"][0]["nativeStatus"], native)

    def test_exemption_is_pass_with_native_metadata_and_no_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "large.py", 7)
            config = write_config(root, {"warnAt": 3, "failAt": 6, "allowedLargeFiles": [{"path": "large.py", "reason": "Approved cohesive module."}]})
            result = self.run_guard(root, ".", "--config", str(config), "--json")
            finding = self.findings(result)[0]
            self.assertEqual((result.returncode, self.read_json(result)["overall"]), (0, "pass"))
            self.assertEqual(self.read_json(result)["requiredPolicies"], [])
            self.assertEqual((finding["state"], finding["nativeStatus"], finding["reason"]), ("pass", "exempt", "Approved cohesive module."))

    def test_ci_changes_only_review_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "review.py", 4)
            self.assertEqual(self.run_guard(root, ".", "--warn", "3", "--fail", "6", "--ci").returncode, 0)
            write_lines(root / "review.py", 7)
            self.assertEqual(self.run_guard(root, ".", "--warn", "3", "--fail", "6", "--ci").returncode, 2)
            config = write_config(root, {"overrides": [{"match": ["*.py"], "warnAt": True, "failAt": 6}]})
            self.assertEqual(self.run_guard(root, ".", "--config", str(config), "--ci", "--json").returncode, 3)

    def test_disabled_loc_has_no_findings_or_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "large.py", 700)
            config = write_config(root, {"enabled": False})
            result = self.run_guard(root, ".", "--config", str(config), "--json")
            self.assertEqual(self.read_json(result), {
                "overall": "pass",
                "scope": {"selected": 2, "analyzed": 1, "inapplicable": 1, "excluded": 0},
                "requiredPolicies": [], "guards": {
                "loc": {"state": "pass", "findings": []},
                "callableSize": {"state": "pass", "findings": []},
                "nesting": {"state": "pass", "findings": []},
                "complexity": {"state": "pass", "findings": []},
                "markdownDocumentSize": {"state": "pass", "findings": []},
                "markdownSectionSize": {"state": "pass", "findings": []},
            }})
