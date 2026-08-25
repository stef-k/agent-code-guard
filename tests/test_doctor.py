from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent_code_guard import code_guard, doctor


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
        launcher = root / "code-guard"
        launcher.touch()
        skill = root / "skill"
        skill.mkdir()
        distribution = SimpleNamespace(
            version="1.2.3",
            entry_points=[SimpleNamespace(group="console_scripts", name="code-guard", value="agent_code_guard.code_guard:main")],
        )
        provider = Mock()
        provider.parse.return_value = object()
        with (
            patch.object(sys, "argv", [str(launcher), "doctor"]),
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
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.healthy_report(root)
            self.assertEqual(
                list(report),
                ["schemaVersion", "status", "distribution", "python", "entryPoint", "skill", "configuration", "git", "providers"],
            )
            self.assertEqual(report["status"], "healthy")
            self.assertEqual([item["name"] for item in report["providers"]["languages"]], LANGUAGES)
            with patch.object(code_guard, "gather_doctor_report", return_value=report):
                human = self.run_main("doctor")
                machine = self.run_main("doctor", "--json")
            self.assertEqual(human[0], 0)
            self.assertEqual(human[2], "")
            self.assertEqual(human[1], doctor.format_human(report) + "\n")
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

    def test_reservation_rejection_and_early_dispatch_preserve_analysis_paths(self) -> None:
        healthy = {"status": "healthy"}
        forbidden = ["validate_configuration", "resolve_scope", "run_analysis", "installed_skill_path", "export_skill"]
        mocks = [patch.object(code_guard, name).start() for name in forbidden]
        self.addCleanup(lambda: [patch.stopall()])
        with patch.object(code_guard, "gather_doctor_report", return_value=healthy):
            self.assertEqual(self.run_main("doctor")[0], 0)
        for mocked in mocks:
            mocked.assert_not_called()

        with patch.object(code_guard, "resolve_scope", side_effect=RuntimeError("analysis entered")):
            self.assertEqual(self.run_main("./doctor")[0], 3)
        self.assertEqual(self.run_main("doctor", "extra.py")[0], 3)
        self.assertEqual(self.run_main("doctor", "--config", "config.json")[0], 3)


if __name__ == "__main__":
    unittest.main()
