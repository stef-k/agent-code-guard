from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from helpers import CodeGuardTestCase
from agent_code_guard.guards import (
    callable_size,
    complexity,
    loc,
    markdown_document_size,
    markdown_section_size,
    nesting,
)


class ConfigurationValidationTests(CodeGuardTestCase):
    def write_config(self, root: Path, document: object) -> Path:
        path = root / "config.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_unknown_keys_report_complete_paths(self) -> None:
        cases = [
            ({"unknown": True}, "unknown"),
            ({"gruds": {}}, "gruds"),
            ({"scope": {"exlcude": []}}, "scope.exlcude"),
            ({"guards": {"callableSzie": {}}}, "guards.callableSzie"),
            ({"guards": {"callableSize": {"enabeld": False}}}, "guards.callableSize.enabeld"),
            ({"guards": {"nesting": {"reviewAfter": 4}}}, "guards.nesting.reviewAfter"),
            ({"guards": {"cyclomaticComplexity": {"warnAt": 4}}}, "guards.cyclomaticComplexity.warnAt"),
            ({"guards": {"markdownDocumentSize": {"reviewAfter": 800}}}, "guards.markdownDocumentSize.reviewAfter"),
            ({"guards": {"markdownSectionSize": {"reviewAfter": 200}}}, "guards.markdownSectionSize.reviewAfter"),
            ({"guards": {"loc": {"warningAt": 400}}}, "guards.loc.warningAt"),
            (
                {"guards": {"loc": {"allowedLargeFiles": [{"path": "legacy.py", "reson": "legacy"}]}}},
                "guards.loc.allowedLargeFiles[0].reson",
            ),
            (
                {"guards": {"loc": {"overrides": [{"match": ["generated/**"], "warn": 100, "failAt": 200}]}}},
                "guards.loc.overrides[0].warn",
            ),
            (
                {"guards": {"callableSize": {"enabled": False, "revieAt": 100}}},
                "guards.callableSize.revieAt",
            ),
            (
                {"guards": {"nesting": {"zzz": 1}, "callableSize": {"aaa": 1}}},
                "guards.callableSize.aaa",
            ),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "valid.py").write_text("value = 1\n", encoding="utf-8")
            for index, (document, path) in enumerate(cases):
                with self.subTest(path=path):
                    config = self.write_config(root, document)
                    result = self.run_guard(root, "valid.py", "--config", str(config), "--json")
                    self.assertEqual(result.returncode, 3)
                    self.assertEqual(
                        self.read_json(result),
                        {"error": f"unknown configuration property: {path}"},
                    )

    def test_valid_configuration_contracts_continue_to_load(self) -> None:
        representative = {
            "version": 1,
            "scope": {"exclude": ["vendor/**"]},
            "guards": {
                "loc": {
                    "enabled": True,
                    "warnAt": 10,
                    "failAt": 20,
                    "countBlankLines": False,
                    "countCommentLines": True,
                    "includeExtensions": [".py"],
                    "exclude": [],
                    "allowedLargeFiles": [{"path": "legacy.py", "reason": "legacy"}],
                    "overrides": [{"match": ["generated/**"], "warnAt": 5, "failAt": 8}],
                },
                "callableSize": {"enabled": False, "reviewAt": "ignored"},
                "nesting": {"enabled": False, "reviewAt": "ignored"},
                "cyclomaticComplexity": {"enabled": False, "reviewAt": "ignored"},
                "markdownDocumentSize": {"enabled": False, "reviewAt": "ignored"},
                "markdownSectionSize": {"enabled": False, "reviewAt": "ignored"},
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "valid.py").write_text("value = 1\n", encoding="utf-8")
            documents = [{}, {"version": 1}, representative]
            for document in documents:
                with self.subTest(document=document):
                    config = self.write_config(root, document)
                    result = self.run_guard(root, "valid.py", "--config", str(config), "--json")
                    self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

            example = Path(__file__).resolve().parents[1] / "examples" / "code-guard.config.json"
            result = self.run_guard(root, "valid.py", "--config", str(example), "--json")
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_example_configuration_preserves_all_builtin_guard_defaults(self) -> None:
        example = Path(__file__).resolve().parents[1] / "examples" / "code-guard.config.json"
        args = SimpleNamespace(
            config=str(example), warn=None, fail=None, include=[], exclude=[],
            count_blank_lines=False, ignore_comment_lines=False,
        )

        loc_config = loc.load_config(args)
        self.assertEqual((loc_config.enabled, loc_config.warn_at, loc_config.fail_at), (True, 400, 600))
        for loader, expected in (
            (callable_size.load_config, 80),
            (nesting.load_config, 4),
            (complexity.load_config, 15),
            (markdown_document_size.load_config, 800),
            (markdown_section_size.load_config, 200),
        ):
            with self.subTest(loader=loader.__module__):
                config = loader(args)
                self.assertEqual((config.enabled, config.review_at), (True, expected))

    def test_original_typo_precedes_valid_and_malformed_source_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.write_config(root, {"guards": {"callableSize": {"enabeld": False}}})
            (root / "valid.py").write_text("value = 1\n", encoding="utf-8")
            (root / "malformed.py").write_text("def broken(:\n", encoding="utf-8")
            expected = {"error": "unknown configuration property: guards.callableSize.enabeld"}
            for source in ("valid.py", "malformed.py"):
                with self.subTest(source=source):
                    result = self.run_guard(root, source, "--config", str(config), "--json")
                    self.assertEqual(result.returncode, 3)
                    self.assertEqual(self.read_json(result), expected)

    def test_scope_typo_precedes_source_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.write_config(root, {"scope": {"exlcude": ["malformed.py"]}})
            (root / "malformed.py").write_text("def broken(:\n", encoding="utf-8")
            result = self.run_guard(root, "malformed.py", "--config", str(config), "--json")
            self.assertEqual(result.returncode, 3)
            self.assertEqual(
                self.read_json(result),
                {"error": "unknown configuration property: scope.exlcude"},
            )

    def test_human_unknown_key_error_uses_existing_error_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "valid.py").write_text("value = 1\n", encoding="utf-8")
            config = self.write_config(root, {"gruds": {}})
            result = self.run_guard(root, "valid.py", "--config", str(config))
            self.assertEqual(result.returncode, 3)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr.strip(), "Code Guard error: unknown configuration property: gruds")


if __name__ == "__main__":
    import unittest

    unittest.main()
