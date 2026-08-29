from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import benchmark_wayfarer


class BenchmarkWayfarerTests(unittest.TestCase):
    def test_target_output_is_rejected_before_directory_creation(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            target = Path(value)
            config = target.parent / "benchmark-config.json"
            config.write_text("{}", encoding="utf-8")

            with patch.object(Path, "mkdir", side_effect=AssertionError("output directory created")):
                with self.assertRaisesRegex(ValueError, "outside the disposable Wayfarer checkout"):
                    benchmark_wayfarer.main([
                        "--wayfarer-path", str(target),
                        "--config-path", str(config),
                        "--output-directory", str(target),
                    ])

    def test_external_and_similarly_prefixed_sibling_outputs_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            parent = Path(value)
            target = parent / "Wayfarer"
            target.mkdir()

            for output in (parent / "results", parent / "Wayfarer-other"):
                self.assertEqual(
                    benchmark_wayfarer.validate_output_directory(target, output),
                    output.absolute(),
                )

    def test_descendant_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            target = Path(value) / "Wayfarer"
            target.mkdir()

            with self.assertRaisesRegex(ValueError, "outside the disposable Wayfarer checkout"):
                benchmark_wayfarer.validate_output_directory(target, target / "results")

    def test_failed_pre_run_git_status_is_rejected(self) -> None:
        failed = subprocess.CompletedProcess([], 1, stdout="possibly clean", stderr="failure")
        with patch.object(benchmark_wayfarer.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "pre-run Git status verification failed"):
                benchmark_wayfarer.git_status(Path("checkout"), "pre-run")

    def test_failed_post_run_git_status_is_rejected(self) -> None:
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="failure")
        with patch.object(benchmark_wayfarer.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "post-run Git status verification failed"):
                benchmark_wayfarer.git_status(Path("checkout"), "post-run")


if __name__ == "__main__":
    unittest.main()
