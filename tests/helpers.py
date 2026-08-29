from __future__ import annotations

import json
import dataclasses
import subprocess
import sys
import unittest
from pathlib import Path

from agent_code_guard.invocation import SelectedFile


def selected_files(paths) -> tuple[SelectedFile, ...]:
    return tuple(SelectedFile(Path(path).as_posix(), Path(path)) for path in paths)


def analyze_source_paths(paths, provider=None):
    """Adapt direct test paths without adding a second production API."""
    from agent_code_guard.analysis.pipeline import analyze_files
    facts = analyze_files(selected_files(paths), provider)
    return dataclasses.replace(
        facts,
        files=tuple(dataclasses.replace(file, reporting_path=None) for file in facts.files),
    )


def analyze_source_paths_for_runner(paths, provider=None):
    from agent_code_guard.analysis.pipeline import analyze_files_for_runner
    return analyze_files_for_runner(selected_files(paths), provider)


def analyze_markdown_paths(paths):
    from agent_code_guard.markdown import analyze_files
    facts = analyze_files(selected_files(paths))
    return dataclasses.replace(
        facts,
        documents=tuple(dataclasses.replace(document, reporting_path=None) for document in facts.documents),
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_GUARD = REPO_ROOT / "skills" / "code-guard" / "scripts" / "code_guard.py"


def write_lines(path: Path, count: int, prefix: str = "line") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    statements = {
        ".py": lambda index: f"{prefix}_{index} = {index}\n",
        ".kt": lambda index: f"val {prefix}{index} = {index}\n",
        ".ts": lambda index: f"const {prefix}{index} = {index};\n",
        ".swift": lambda index: f"let {prefix}{index} = {index}\n",
        ".vue": lambda index: "<template />\n",
    }
    render = statements.get(path.suffix, lambda index: f"{prefix} {index}\n")
    path.write_text("".join(render(index) for index in range(count)), encoding="utf-8")


def write_config(root: Path, loc: object, **document: object) -> Path:
    path = root / "code-guard.config.json"
    payload = {"version": 1, "guards": {"loc": loc}, **document}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


def init_git(root: Path) -> None:
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "tests@example.com")
    git(root, "config", "user.name", "Code Guard Tests")


class CodeGuardTestCase(unittest.TestCase):
    def run_guard(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CODE_GUARD), *args], cwd=root, text=True, capture_output=True,
        )

    def read_json(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        return json.loads(result.stdout)

    def findings(self, result: subprocess.CompletedProcess[str]) -> list[dict[str, object]]:
        return self.read_json(result)["guards"]["loc"]["findings"]

    def assert_syntax_unavailable(self, result: subprocess.CompletedProcess[str], path: str) -> None:
        data = self.read_json(result)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(data["overall"], "incomplete")
        self.assertEqual(data["scope"]["unavailable"], 1)
        self.assertEqual(data["unavailable"][0]["path"], path)
        self.assertEqual(data["unavailable"][0]["kind"], "syntax")
