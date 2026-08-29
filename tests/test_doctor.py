from __future__ import annotations

import json
import importlib
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_PACKAGE = "_doctor_checkout_agent_code_guard"
package = types.ModuleType(CHECKOUT_PACKAGE)
package.__path__ = [str(REPO_ROOT / "src" / "agent_code_guard")]
sys.modules[CHECKOUT_PACKAGE] = package
code_guard = importlib.import_module(f"{CHECKOUT_PACKAGE}.code_guard")
doctor = importlib.import_module(f"{CHECKOUT_PACKAGE}.doctor")
regions = importlib.import_module(f"{CHECKOUT_PACKAGE}.analysis.regions")


LANGUAGES = [
    "python", "go", "kotlin", "csharp", "java", "javascript", "typescript",
    "tsx", "cpp", "rust", "php", "swift", "dart", "vue",
]


class DoctorTests(unittest.TestCase):
    def run_main(self, *arguments: str) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.object(sys, "argv", ["code-guard", *arguments]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = code_guard.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def healthy_report(self, root: Path) -> dict[str, object]:
        launcher = root / "code-guard.exe"
        launcher.touch()
        skill = root / "skill"
        skill.mkdir()
        distribution = SimpleNamespace(
            version="1.2.3",
            entry_points=[SimpleNamespace(group="console_scripts", name="code-guard", value="agent_code_guard.code_guard:main")],
            files=[Path("../Scripts/code-guard.exe")],
            locate_file=lambda item: launcher,
        )
        provider = Mock()
        provider.parse.return_value = object()
        with (
            patch.object(sys, "argv", [str(root / "code-guard"), "doctor"]),
            patch.object(doctor.platform, "system", return_value="Windows"),
            patch.object(doctor.metadata, "distribution", return_value=distribution),
            patch.object(doctor.metadata, "version", side_effect=["0.26.0", "1.14.3"]),
            patch.object(doctor, "installed_skill_path", return_value=skill),
            patch.object(doctor, "TreeSitterProvider", return_value=provider),
            patch.object(doctor.shutil, "which", return_value=str(root / "git.exe")) as which,
            patch.object(doctor.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=str(root), stderr="")),
            patch.object(Path, "cwd", return_value=root),
        ):
            report = doctor.gather_report()
        which.assert_called_once_with("git")
        self.assertEqual([call.args for call in provider.parse.call_args_list], [(language, b"") for language in LANGUAGES])
        return report

    def test_healthy_human_and_json_are_exact_ordered_stdout_only_reports(self) -> None:
        help_text = code_guard.parser().format_help()
        for fragment in (
            "code-guard doctor", "code-guard doctor --json", "Healthy reports exit 0",
            "unhealthy reports exit 1", "errors exit 3",
        ):
            self.assertIn(fragment, help_text)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.healthy_report(root)
            self.assertEqual(
                list(report),
                ["schemaVersion", "status", "distribution", "python", "entryPoint", "skill", "configuration", "git", "providers"],
            )
            self.assertEqual(list(report["distribution"]), ["name", "version", "status", "message"])
            self.assertEqual(list(report["python"]), ["implementation", "version", "executable", "status", "message"])
            self.assertEqual(
                list(report["entryPoint"]),
                ["name", "target", "invoked", "resolvedPath", "kind", "status", "message"],
            )
            self.assertEqual(list(report["skill"]), ["available", "path", "status", "message"])
            self.assertEqual(list(report["configuration"]), ["mode", "path", "valid", "status", "message"])
            self.assertEqual(
                list(report["git"]),
                ["executableAvailable", "executable", "repositoryAvailable", "root", "status", "message"],
            )
            self.assertEqual(list(report["providers"]), ["status", "message", "distributions", "languages"])
            self.assertEqual(report["status"], "healthy")
            self.assertEqual(report["entryPoint"]["invoked"], str(root / "code-guard"))
            self.assertEqual(report["entryPoint"]["resolvedPath"], str((root / "code-guard.exe").resolve()))
            self.assertEqual(report["entryPoint"]["kind"], "console-script")
            self.assertEqual([item["name"] for item in report["providers"]["languages"]], LANGUAGES)
            self.assertEqual(doctor.PROVIDER_LANGUAGES, regions.PROVIDER_LANGUAGES)
            with patch.object(code_guard, "gather_doctor_report", return_value=report):
                human = self.run_main("doctor")
                machine = self.run_main("doctor", "--json")
            self.assertEqual(human[0], 0)
            self.assertEqual(human[2], "")
            self.assertEqual(human[1], "\n".join((
                "Code Guard doctor: HEALTHY",
                "Distribution: OK agent-code-guard 1.2.3",
                f"Python: OK {report['python']['implementation']} {report['python']['version']} ({report['python']['executable']})",
                f"Entry point: OK code-guard -> agent_code_guard.code_guard:main (console-script; {report['entryPoint']['resolvedPath']})",
                f"Skill: OK {report['skill']['path']}",
                "Configuration: OK defaults (no configuration file)",
                f"Git: OK {report['git']['executable']}; repository {report['git']['root']}",
                "Providers: OK tree-sitter 0.26.0; tree-sitter-language-pack 1.14.3; 14/14 languages available",
                "",
            )))
            self.assertEqual(machine[0], 0)
            self.assertEqual(machine[2], "")
            self.assertEqual(json.loads(machine[1]), report)

    def test_partial_provider_failure_is_safe_unhealthy_and_does_not_stop_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = Mock()
            provider.parse.side_effect = [RuntimeError("private token=secret"), *([object()] * 13)]
            with (
                patch.object(sys, "argv", [str(root / "missing-launcher"), "doctor"]),
                patch.object(doctor.metadata, "distribution", side_effect=OSError("private metadata")),
                patch.object(doctor.metadata, "version", side_effect=["0.26.0", "1.14.3"]),
                patch.object(doctor, "installed_skill_path", side_effect=ValueError("private skill")),
                patch.object(doctor, "TreeSitterProvider", return_value=provider),
                patch.object(doctor.shutil, "which", return_value=str(root / "git")),
                patch.object(doctor.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="fatal")) as git,
                patch.object(Path, "cwd", return_value=root),
            ):
                report = doctor.gather_report()
            self.assertEqual(report["status"], "unhealthy")
            self.assertEqual(report["providers"]["languages"][0]["status"], "unavailable")
            self.assertEqual(report["providers"]["languages"][-1]["status"], "ok")
            self.assertNotIn("secret", json.dumps(report))
            self.assertEqual(provider.parse.call_count, 14)
            git.assert_called_once()
            with patch.object(code_guard, "gather_doctor_report", return_value=report):
                self.assertEqual(self.run_main("doctor", "--json")[0], 1)

        with (
            patch.object(doctor, "_git", side_effect=RuntimeError("private failure")),
            patch.object(doctor, "_providers", return_value=report["providers"]) as providers,
        ):
            continued = doctor.gather_report()
        self.assertEqual(continued["git"]["message"], "Git check failed")
        providers.assert_called_once()

    def test_reservation_rejection_and_early_dispatch_preserve_analysis_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            unrelated = Path(temp) / "code_guard.py"
            unrelated.touch()
            distribution = SimpleNamespace(
                entry_points=[SimpleNamespace(group="console_scripts", name="code-guard", value="agent_code_guard.code_guard:main")],
                files=[],
            )
            with patch.object(sys, "argv", [str(unrelated), "doctor"]):
                entry = doctor._entry_point(distribution)
            self.assertEqual(entry["kind"], "other")
            self.assertEqual(entry["status"], "unavailable")

        healthy = {"status": "healthy"}
        forbidden = [
            "load_configuration", "validate_configuration", "resolve_invocation",
            "run_analysis", "installed_skill_path", "export_skill",
        ]
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch.object(code_guard, name)) for name in forbidden]
            stack.enter_context(patch.object(code_guard, "gather_doctor_report", return_value=healthy))
            self.assertEqual(self.run_main("doctor", "--json")[0], 0)
            for mocked in mocks:
                mocked.assert_not_called()

        with patch.object(code_guard, "resolve_invocation", side_effect=RuntimeError("qualified path analyzed")) as resolve:
            self.assertEqual(self.run_main("./doctor")[0], 3)
            resolve.assert_called_once()
        self.assertEqual(self.run_main("doctor", "extra.py")[0], 3)
        self.assertEqual(self.run_main("doctor", "--config", "config.json")[0], 3)


if __name__ == "__main__":
    unittest.main()
