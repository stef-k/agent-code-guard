from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_GUARD = REPO_ROOT / "skills" / "code-guard" / "scripts" / "code_guard.py"

class InstalledPackageTests(unittest.TestCase):
    def test_distribution_declares_canonical_runtime_dependencies(self) -> None:
        requirements = importlib.metadata.requires("agent-code-guard") or []
        self.assertEqual(
            requirements,
            ["tree-sitter==0.26.0", "tree-sitter-language-pack==1.14.3"],
        )

    def test_console_command_runs_loc_without_loading_analysis_modules(self) -> None:
        script = """
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from agent_code_guard.code_guard import main

with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / "sample.py"
    path.write_text("value = 1\\n", encoding="utf-8")
    config = Path(temp) / "config.json"
    config.write_text('{"guards":{"callableSize":{"enabled":false},"nesting":{"enabled":false}}}', encoding="utf-8")
    with patch.object(sys, "argv", ["code-guard", str(path), "--config", str(config), "--json"]):
        result = main()

loaded = sorted(name for name in sys.modules if name.startswith(("agent_code_guard.analysis", "tree_sitter")))
print(json.dumps({"result": result, "loaded": loaded}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script], text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(json.loads(lines[-1]), {"result": 0, "loaded": []})

    def test_installed_syntax_pipeline_loads_parser_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.py"
            path.write_text("def answer():\n    return 42\n", encoding="utf-8")
            script = (
                "import sys; from pathlib import Path; "
                "from agent_code_guard.analysis.pipeline import analyze_files; "
                "facts = analyze_files([Path(sys.argv[1])]); "
                "assert [item.identity for item in facts.callables] == ['sample.answer']"
            )
            result = subprocess.run(
                [sys.executable, "-c", script, str(path)], text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_checkout_compatibility_launcher_finds_source_package(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", str(CODE_GUARD), "--help"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Run deterministic Code Guard checks.", result.stdout)


if __name__ == "__main__":
    unittest.main()
