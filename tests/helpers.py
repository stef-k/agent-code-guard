from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

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
