from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agent_code_guard.code_guard import main


COMPATIBILITY_RUNNER = REPO_ROOT / "skills" / "code-guard" / "scripts" / "code_guard.py"
DISTRIBUTION = "agent-code-guard"


class CliVersionTests(unittest.TestCase):
    def run_main(self, *arguments: str) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.object(sys, "argv", ["code-guard", *arguments]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_human_version_uses_distribution_metadata_exactly(self) -> None:
        with patch("agent_code_guard.code_guard.distribution_version", return_value="9.8.7+local") as version:
            result = self.run_main("--version")

        self.assertEqual(result, (0, "agent-code-guard 9.8.7+local\n", ""))
        version.assert_called_once_with(DISTRIBUTION)

    def test_json_version_has_exact_stable_shape(self) -> None:
        with patch("agent_code_guard.code_guard.distribution_version", return_value="9.8.7"):
            code, stdout, stderr = self.run_main("--version", "--json")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), {"distribution": DISTRIBUTION, "version": "9.8.7"})

    def test_metadata_failure_uses_deterministic_human_error(self) -> None:
        error = importlib.metadata.PackageNotFoundError(DISTRIBUTION)
        with patch("agent_code_guard.code_guard.distribution_version", side_effect=error):
            result = self.run_main("--version")

        self.assertEqual(
            result,
            (3, "", "Code Guard error: installed distribution metadata is unavailable for agent-code-guard\n"),
        )
        self.assertNotIn("Traceback", "".join(result[1:]))
        self.assertNotIn(str(error), "".join(result[1:]))

    def test_metadata_failure_uses_deterministic_json_error(self) -> None:
        error = importlib.metadata.PackageNotFoundError(DISTRIBUTION)
        with patch("agent_code_guard.code_guard.distribution_version", side_effect=error):
            code, stdout, stderr = self.run_main("--version", "--json")

        self.assertEqual(code, 3)
        self.assertEqual(stderr, "")
        self.assertEqual(
            json.loads(stdout),
            {"error": "installed distribution metadata is unavailable for agent-code-guard"},
        )
        self.assertNotIn("Traceback", stdout)
        self.assertNotIn(str(error), stdout)

    def test_version_returns_before_analysis_configuration_scope_and_skill_work(self) -> None:
        forbidden_calls = [
            "validate_configuration",
            "resolve_scope",
            "run_guards",
            "installed_skill_path",
            "export_skill",
        ]
        patches = [patch(f"agent_code_guard.code_guard.{name}") for name in forbidden_calls]
        mocks = [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])

        with patch("agent_code_guard.code_guard.distribution_version", return_value="1.2.3"):
            self.assertEqual(self.run_main("--version"), (0, "agent-code-guard 1.2.3\n", ""))

        for mocked in mocks:
            mocked.assert_not_called()

    def test_version_does_not_import_or_initialize_providers(self) -> None:
        script = """
import json
import sys
from unittest.mock import patch
from agent_code_guard.code_guard import main
with patch.object(sys, 'argv', ['code-guard', '--version']):
    result = main()
loaded = sorted(name for name in sys.modules if name.startswith(
    ('agent_code_guard.analysis', 'agent_code_guard.markdown', 'tree_sitter')
))
print(json.dumps({'result': result, 'loaded': loaded}))
"""
        result = subprocess.run([sys.executable, "-c", script], text=True, capture_output=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]), {"result": 0, "loaded": []})

    def test_version_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before = list(root.rglob("*"))
            with patch("agent_code_guard.code_guard.distribution_version", return_value="1.2.3"):
                with patch("pathlib.Path.cwd", return_value=root):
                    self.assertEqual(self.run_main("--version")[0], 0)
            self.assertEqual(list(root.rglob("*")), before)

    def test_version_rejects_every_non_json_argument_category(self) -> None:
        cases = {
            "path": ["sample.py"],
            "config": ["--config", "config.json"],
            "loc_warn": ["--warn", "10"],
            "loc_fail": ["--fail", "20"],
            "loc_include": ["--include", ".txt"],
            "loc_exclude": ["--exclude", "vendor/**"],
            "scope_exclude": ["--scope-exclude", "generated/**"],
            "count_blank": ["--count-blank-lines"],
            "ignore_comments": ["--ignore-comment-lines"],
            "changed": ["--changed-only"],
            "staged": ["--staged"],
            "base_ref": ["--base-ref", "main"],
            "ci": ["--ci"],
            "skill_path": ["--skill-path"],
            "export_skill": ["--export-skill", "target"],
        }
        for name, arguments in cases.items():
            for json_arguments in ([], ["--json"]):
                with self.subTest(category=name, json=bool(json_arguments)):
                    code, stdout, stderr = self.run_main("--version", *arguments, *json_arguments)
                    self.assertEqual(code, 3)
                    if json_arguments:
                        self.assertEqual(stderr, "")
                        self.assertEqual(set(json.loads(stdout)), {"error"})
                    else:
                        self.assertEqual(stdout, "")
                        self.assertTrue(stderr.startswith("Code Guard error: "))

    def test_checkout_compatibility_runner_matches_console_behavior(self) -> None:
        expected_version = importlib.metadata.version(DISTRIBUTION)
        for arguments in (["--version"], ["--version", "--json"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-I", str(COMPATIBILITY_RUNNER), *arguments],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                if "--json" in arguments:
                    self.assertEqual(
                        json.loads(result.stdout),
                        {"distribution": DISTRIBUTION, "version": expected_version},
                    )
                else:
                    self.assertEqual(result.stdout, f"{DISTRIBUTION} {expected_version}\n")

    def test_non_version_cli_behavior_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.py"
            source.write_text("answer = 42\n", encoding="utf-8")
            config = root / "config.json"
            config.write_text(
                '{"guards":{"callableSize":{"enabled":false},"nesting":{"enabled":false},'
                '"cyclomaticComplexity":{"enabled":false},"markdownDocumentSize":{"enabled":false},'
                '"markdownSectionSize":{"enabled":false}}}',
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(COMPATIBILITY_RUNNER), str(source), "--config", str(config), "--json"],
                cwd=root,
                text=True,
                capture_output=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["overall"], "pass")


if __name__ == "__main__":
    unittest.main()
