from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

CHECKOUT_PACKAGE = "_checkout_agent_code_guard"


def _load_checkout_code_guard():
    package = types.ModuleType(CHECKOUT_PACKAGE)
    package.__path__ = [str(REPO_ROOT / "src" / "agent_code_guard")]
    module_name = f"{CHECKOUT_PACKAGE}.code_guard"
    module_spec = importlib.util.spec_from_file_location(
        module_name, REPO_ROOT / "src" / "agent_code_guard" / "code_guard.py",
    )
    assert module_spec is not None and module_spec.loader is not None
    checkout_module = importlib.util.module_from_spec(module_spec)
    sys.modules[CHECKOUT_PACKAGE] = package
    sys.modules[module_name] = checkout_module
    try:
        module_spec.loader.exec_module(checkout_module)
    finally:
        for loaded_name in tuple(sys.modules):
            if loaded_name == CHECKOUT_PACKAGE or loaded_name.startswith(f"{CHECKOUT_PACKAGE}."):
                del sys.modules[loaded_name]
    return checkout_module


checkout_code_guard = _load_checkout_code_guard()
main = checkout_code_guard.main


COMPATIBILITY_RUNNER = REPO_ROOT / "skills" / "code-guard" / "scripts" / "code_guard.py"
DISTRIBUTION = "agent-code-guard"
METADATA_UNAVAILABLE = f"installed distribution metadata is unavailable for {DISTRIBUTION}"


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
        with patch.object(checkout_code_guard, "distribution_version", return_value="9.8.7+local") as version:
            result = self.run_main("--version")

        self.assertEqual(result, (0, "agent-code-guard 9.8.7+local\n", ""))
        version.assert_called_once_with(DISTRIBUTION)

    def test_help_documents_version_invocations_outputs_and_exits(self) -> None:
        help_text = checkout_code_guard.parser().format_help()

        for fragment in (
            "code-guard --version",
            "code-guard --version --json",
            "agent-code-guard <version>",
            '"distribution"',
            '"version"',
            "exits 0",
            "exit 3",
            "--version may be combined only with --json",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, help_text)

        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.object(sys, "argv", ["code-guard", "--help"]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as exit_context,
        ):
            main()

        self.assertEqual(exit_context.exception.code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(stdout.getvalue(), help_text)

    def test_json_version_has_exact_stable_shape(self) -> None:
        with patch.object(checkout_code_guard, "distribution_version", return_value="9.8.7"):
            code, stdout, stderr = self.run_main("--version", "--json")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), {"distribution": DISTRIBUTION, "version": "9.8.7"})

    def test_metadata_failure_uses_deterministic_human_error(self) -> None:
        for error in (importlib.metadata.PackageNotFoundError(DISTRIBUTION), OSError("private detail")):
            with self.subTest(error=type(error).__name__):
                with patch.object(checkout_code_guard, "distribution_version", side_effect=error):
                    result = self.run_main("--version")

                self.assertEqual(
                    result,
                    (3, "", "Code Guard error: installed distribution metadata is unavailable for agent-code-guard\n"),
                )
                self.assertNotIn("Traceback", "".join(result[1:]))
                self.assertNotIn(str(error), "".join(result[1:]))

    def test_metadata_failure_uses_deterministic_json_error(self) -> None:
        for error in (importlib.metadata.PackageNotFoundError(DISTRIBUTION), OSError("private detail")):
            with self.subTest(error=type(error).__name__):
                with patch.object(checkout_code_guard, "distribution_version", side_effect=error):
                    code, stdout, stderr = self.run_main("--version", "--json")

                self.assertEqual(code, 3)
                self.assertEqual(stderr, "")
                self.assertEqual(
                    json.loads(stdout),
                    {"error": "installed distribution metadata is unavailable for agent-code-guard"},
                )
                self.assertNotIn("Traceback", stdout)
                self.assertNotIn(str(error), stdout)

    def test_unicode_decode_error_uses_deterministic_human_error(self) -> None:
        error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        with patch.object(checkout_code_guard, "distribution_version", side_effect=error):
            result = self.run_main("--version")

        self.assertEqual(
            result,
            (3, "", "Code Guard error: installed distribution metadata is unavailable for agent-code-guard\n"),
        )
        self.assertNotIn(str(error), "".join(result[1:]))

    def test_unicode_decode_error_uses_deterministic_json_error(self) -> None:
        error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        with patch.object(checkout_code_guard, "distribution_version", side_effect=error):
            code, stdout, stderr = self.run_main("--version", "--json")

        self.assertEqual(code, 3)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), {"error": METADATA_UNAVAILABLE})
        self.assertNotIn(str(error), stdout)

    def test_non_string_metadata_uses_deterministic_human_error(self) -> None:
        with patch.object(checkout_code_guard, "distribution_version", return_value=None):
            result = self.run_main("--version")

        self.assertEqual(result, (3, "", f"Code Guard error: {METADATA_UNAVAILABLE}\n"))

    def test_non_string_metadata_uses_deterministic_json_error(self) -> None:
        with patch.object(checkout_code_guard, "distribution_version", return_value=None):
            code, stdout, stderr = self.run_main("--version", "--json")

        self.assertEqual(code, 3)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), {"error": METADATA_UNAVAILABLE})

    def test_version_returns_before_analysis_configuration_scope_and_skill_work(self) -> None:
        forbidden_calls = [
            "validate_configuration",
            "resolve_scope",
            "run_guards",
            "installed_skill_path",
            "export_skill",
        ]
        patches = [patch.object(checkout_code_guard, name) for name in forbidden_calls]
        mocks = [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])

        with patch.object(checkout_code_guard, "distribution_version", return_value="1.2.3"):
            self.assertEqual(self.run_main("--version"), (0, "agent-code-guard 1.2.3\n", ""))

        for mocked in mocks:
            mocked.assert_not_called()

    def test_version_does_not_import_or_initialize_providers(self) -> None:
        script = """
import json
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from agent_code_guard.code_guard import main
with patch.object(sys, 'argv', ['code-guard', '--version']):
    result = main()
loaded = sorted(name for name in sys.modules if name.startswith(
    ('agent_code_guard.analysis', 'agent_code_guard.markdown', 'tree_sitter')
))
print(json.dumps({'result': result, 'loaded': loaded}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(REPO_ROOT / "src")], text=True, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]), {"result": 0, "loaded": []})

    def test_version_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before = list(root.rglob("*"))
            with patch.object(checkout_code_guard, "distribution_version", return_value="1.2.3"):
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
            "help": ["--help"],
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
        sentinel = "parent-metadata-sentinel-that-is-not-a-version"
        parent_version = importlib.metadata.version
        with patch.object(importlib.metadata, "version", return_value=sentinel):
            self.assertEqual(importlib.metadata.version(DISTRIBUTION), sentinel)
            expected = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import importlib.metadata,sys;sys.path.insert(0,sys.argv[1]);"
                    "print(importlib.metadata.version(sys.argv[2]))",
                    str(REPO_ROOT / "src"),
                    DISTRIBUTION,
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(expected.returncode, 0, expected.stderr)
            expected_version = expected.stdout.rstrip("\n")
            self.assertNotEqual(expected_version, sentinel)

            for arguments in (["--version"], ["--version", "--json"]):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [sys.executable, "-I", str(COMPATIBILITY_RUNNER), *arguments],
                        text=True,
                        capture_output=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, "")
                    self.assertNotIn(sentinel, result.stdout)
                    if "--json" in arguments:
                        self.assertEqual(
                            json.loads(result.stdout),
                            {"distribution": DISTRIBUTION, "version": expected_version},
                        )
                    else:
                        self.assertEqual(result.stdout, f"{DISTRIBUTION} {expected_version}\n")

        self.assertIs(importlib.metadata.version, parent_version)

    def test_checkout_loading_does_not_mutate_package_search_path(self) -> None:
        self.assertFalse(any(
            name == CHECKOUT_PACKAGE or name.startswith(f"{CHECKOUT_PACKAGE}.") for name in sys.modules
        ))
        host_package = sys.modules.get("agent_code_guard")
        if host_package is not None:
            self.assertNotIn(str(REPO_ROOT / "src" / "agent_code_guard"), host_package.__path__)

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
