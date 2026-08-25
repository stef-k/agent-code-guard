from __future__ import annotations

import tempfile
from pathlib import Path

from helpers import CodeGuardTestCase, git, init_git, write_config, write_lines


class ScopeCountTests(CodeGuardTestCase):
    def test_empty_changed_scope_reports_zero_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git(root)
            write_lines(root / "tracked.py", 1)
            git(root, "add", ".")
            git(root, "commit", "-m", "base")

            human = self.run_guard(root, "--changed-only")
            json_result = self.run_guard(root, "--changed-only", "--json")

            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertEqual(
                human.stdout.splitlines()[0],
                "PASS: 0 selected; 0 analyzed; 0 inapplicable; 0 excluded.",
            )
            self.assertEqual(json_result.returncode, 0, json_result.stderr)
            self.assertEqual(
                self.read_json(json_result)["scope"],
                {"selected": 0, "analyzed": 0, "inapplicable": 0, "excluded": 0},
            )

    def test_mixed_scope_reports_analyzed_inapplicable_and_excluded_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "analyzed.py", 1)
            (root / "unsupported.txt").write_text("unsupported\n", encoding="utf-8")
            write_lines(root / "excluded.py", 1)
            config = write_config(root, {}, scope={"exclude": ["excluded.py"]})

            paths = ("analyzed.py", "unsupported.txt", "excluded.py")
            human = self.run_guard(root, *paths, "--config", str(config))
            json_result = self.run_guard(root, *paths, "--config", str(config), "--json")

            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertEqual(
                human.stdout.splitlines()[0],
                "PASS: 2 selected; 1 analyzed; 1 inapplicable; 1 excluded.",
            )
            scope = self.read_json(json_result)["scope"]
            self.assertEqual(
                scope,
                {"selected": 2, "analyzed": 1, "inapplicable": 1, "excluded": 1},
            )
            self.assertEqual(scope["analyzed"] + scope["inapplicable"], scope["selected"])

    def test_review_state_and_exit_are_preserved_with_scope_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_lines(root / "review.py", 2)
            config = write_config(root, {"warnAt": 1, "failAt": 3})

            human = self.run_guard(root, "review.py", "--config", str(config))
            json_result = self.run_guard(root, "review.py", "--config", str(config), "--json")

            self.assertEqual(human.returncode, 1, human.stderr)
            self.assertEqual(
                human.stdout.splitlines()[0],
                "REVIEW: 1 selected; 1 analyzed; 0 inapplicable; 0 excluded.",
            )
            payload = self.read_json(json_result)
            self.assertEqual((json_result.returncode, payload["overall"]), (1, "review"))
            self.assertEqual(
                payload["scope"],
                {"selected": 1, "analyzed": 1, "inapplicable": 0, "excluded": 0},
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
