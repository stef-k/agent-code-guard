from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_code_guard import skill_distribution
from agent_code_guard.code_guard import main

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_GUARD = REPO_ROOT / "skills" / "code-guard" / "scripts" / "code_guard.py"
SKILL_SOURCE = REPO_ROOT / "skills" / "code-guard"


class SkillDistributionTests(unittest.TestCase):
    def test_payload_manifest_matches_canonical_source_bytes(self) -> None:
        authored_payload = sorted(
            path.relative_to(SKILL_SOURCE).as_posix()
            for path in SKILL_SOURCE.rglob("*")
            if path.is_file() and "scripts" not in path.relative_to(SKILL_SOURCE).parts
        )
        self.assertEqual(sorted(skill_distribution.PAYLOAD_FILES), authored_payload)
        installed = skill_distribution.skill_path()
        for relative in skill_distribution.PAYLOAD_FILES:
            self.assertEqual((installed / relative).read_bytes(), (SKILL_SOURCE / relative).read_bytes())

    def test_management_modes_do_not_load_config_or_resolve_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = Path(temp) / "installed-skill"
            skill.mkdir()
            with (
                patch.object(sys, "argv", ["code-guard", "--skill-path"]),
                patch("agent_code_guard.code_guard.installed_skill_path", return_value=skill),
                patch("agent_code_guard.code_guard.validate_configuration") as validate,
                patch("agent_code_guard.code_guard.resolve_scope") as resolve,
            ):
                self.assertEqual(main(), 0)
            validate.assert_not_called()
            resolve.assert_not_called()

    def test_export_copies_only_manifest_and_adds_distribution_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            installed = root / "installed-skill"
            for relative in skill_distribution.PAYLOAD_FILES:
                source = installed / relative
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes((SKILL_SOURCE / relative).read_bytes())
            target = root / "exported-skill"

            with (
                patch.object(sys, "argv", ["code-guard", "--export-skill", str(target)]),
                patch("agent_code_guard.skill_distribution.skill_path", return_value=installed),
                patch("agent_code_guard.skill_distribution.version", return_value="9.8.7"),
            ):
                self.assertEqual(main(), 0)

            self.assertEqual(
                sorted(path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()),
                sorted([*skill_distribution.PAYLOAD_FILES, ".agent-code-guard-version"]),
            )
            for relative in skill_distribution.PAYLOAD_FILES:
                self.assertEqual((target / relative).read_bytes(), (SKILL_SOURCE / relative).read_bytes())
            self.assertEqual((target / ".agent-code-guard-version").read_text(encoding="utf-8"), "9.8.7\n")

    def test_export_rejects_nonempty_target_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "target"
            target.mkdir()
            existing = target / "keep.txt"
            existing.write_text("keep", encoding="utf-8")
            with patch.object(sys, "argv", ["code-guard", "--export-skill", str(target)]):
                self.assertEqual(main(), 3)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

    def test_management_mode_rejects_guard_arguments(self) -> None:
        cases = [
            ["--skill-path", "--changed-only"],
            ["--skill-path", "--json"],
            ["--export-skill", "target", "src/example.py"],
            ["--skill-path", "--export-skill", "target"],
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments), patch.object(sys, "argv", ["code-guard", *arguments]):
                self.assertEqual(main(), 3)

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
    config.write_text('{"guards":{"callableSize":{"enabled":false},"nesting":{"enabled":false},"cyclomaticComplexity":{"enabled":false},"markdownDocumentSize":{"enabled":false},"markdownSectionSize":{"enabled":false}}}', encoding="utf-8")
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

    def test_installed_package_exposes_production_markdown_without_research_imports(self) -> None:
        script = """
import json
import sys
from pathlib import Path
from agent_code_guard.guards import markdown_document_size, markdown_section_size
from agent_code_guard.markdown import analyze_files
facts = analyze_files([Path(sys.argv[1])])
print(json.dumps({"lines": facts.documents[0].physical_lines,
                  "research": sorted(name for name in sys.modules if name.startswith("research"))}))
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.md"
            path.write_text("# Heading\nbody\n", encoding="utf-8")
            result = subprocess.run([sys.executable, "-c", script, str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"lines": 2, "research": []})

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
