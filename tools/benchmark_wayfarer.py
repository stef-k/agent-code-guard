"""Reproducible, non-CI benchmark for the fixed Wayfarer workload."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_COMMIT = "679ddae9717bf78681a2cfbf794f687127b23b5d"
GUARD_NAMES = (
    "loc",
    "callableSize",
    "nesting",
    "cyclomaticComplexity",
    "markdownDocumentSize",
    "markdownSectionSize",
)


def validate_output_directory(target: Path, output: Path) -> Path:
    """Return a normalized output path only when it is outside the target."""
    target_text = os.path.normcase(os.path.abspath(target))
    output_path = Path(os.path.abspath(output))
    output_text = os.path.normcase(str(output_path))
    try:
        contained = os.path.commonpath((target_text, output_text)) == target_text
    except ValueError:
        contained = False
    if contained:
        raise ValueError("OutputDirectory must be outside the disposable Wayfarer checkout.")
    return output_path


def git_status(target: Path, phase: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip()
        message = f"{phase} Git status verification failed"
        raise RuntimeError(f"{message}: {detail}" if detail else message)
    return result.stdout.rstrip("\r\n")


def checked_output(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip()
        rendered = subprocess.list2cmdline(command)
        raise RuntimeError(f"command failed with exit {result.returncode}: {rendered}{': ' + detail if detail else ''}")
    return (result.stdout or result.stderr).strip()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run_redirected(command: list[str], cwd: Path, stdout: Path, stderr: Path) -> tuple[int, float]:
    started = time.perf_counter()
    with stdout.open("w", encoding="utf-8") as stdout_file, stderr.open("w", encoding="utf-8") as stderr_file:
        result = subprocess.run(command, cwd=cwd, stdout=stdout_file, stderr=stderr_file, check=False)
    return result.returncode, time.perf_counter() - started


def command_text(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--wayfarer-path", required=True)
    result.add_argument("--config-path", required=True)
    result.add_argument("--output-directory", required=True)
    result.add_argument("--python", default="python")
    result.add_argument("--installation-mode", default="installed distribution")
    return result


def main(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    target = Path(args.wayfarer_path).resolve(strict=True)
    config = Path(args.config_path).resolve(strict=True)
    output = validate_output_directory(target, Path(args.output_directory))

    commit = checked_output(["git", "-C", str(target), "rev-parse", "HEAD"])
    if commit != EXPECTED_COMMIT:
        raise RuntimeError(f"Wayfarer must be checked out at {EXPECTED_COMMIT}; found {commit}.")
    before = git_status(target, "pre-run")
    output.mkdir(parents=True, exist_ok=True)

    base = json.loads(config.read_text(encoding="utf-8"))
    guards = base.get("guards") if isinstance(base, dict) else None
    if not isinstance(guards, dict):
        raise ValueError("Normal benchmark configuration must contain a guards object.")
    if set(guards) != set(GUARD_NAMES):
        raise ValueError("Normal benchmark configuration must contain exactly the six shipped guard sections.")
    for guard in GUARD_NAMES:
        if not isinstance(guards[guard], dict) or guards[guard].get("enabled") is not True:
            raise ValueError(f"Normal benchmark configuration must explicitly enable guards.{guard}.")

    def variant(name: str, enabled: set[str]) -> Path:
        document = copy.deepcopy(base)
        for guard in GUARD_NAMES:
            document["guards"][guard]["enabled"] = guard in enabled
        path = output / f"{name}.config.json"
        write_json(path, document)
        return path

    loc_only = variant("loc-only", {"loc"})
    syntax_only = variant("syntax-only", {"callableSize", "nesting", "cyclomaticComplexity"})
    metadata: dict[str, object] = {
        "recordedAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceCommit": commit,
        "configuration": str(config),
        "configurationSha256": hashlib.sha256(config.read_bytes()).hexdigest().upper(),
        "python": checked_output([args.python, "--version"]),
        "codeGuard": checked_output([args.python, "-m", "agent_code_guard.code_guard", "--version"]),
        "installationMode": args.installation_mode,
        "workingDirectory": str(target),
        "samples": {},
    }

    def measure(name: str, variant_config: Path) -> None:
        command = [
            args.python, "-m", "agent_code_guard.code_guard", ".",
            "--config", str(variant_config), "--json", "--ci",
        ]
        warmup_stdout = output / f"{name}.warmup.json"
        warmup_stderr = output / f"{name}.warmup.stderr.txt"
        warmup_exit, _ = run_redirected(command, target, warmup_stdout, warmup_stderr)
        if warmup_exit != 0:
            raise RuntimeError(f"{name} warmup failed with exit {warmup_exit}.")
        samples = []
        for sample in range(1, 4):
            stdout = output / f"{name}.sample-{sample}.json"
            stderr = output / f"{name}.sample-{sample}.stderr.txt"
            exit_code, seconds = run_redirected(command, target, stdout, stderr)
            if exit_code != 0:
                raise RuntimeError(f"{name} sample {sample} failed with exit {exit_code}.")
            samples.append({
                "sample": sample, "seconds": seconds, "exitCode": exit_code,
                "stdout": str(stdout), "stderr": str(stderr),
            })
        ordered = sorted(sample["seconds"] for sample in samples)
        metadata["samples"][name] = {
            "command": command_text(command),
            "warmup": {"exitCode": warmup_exit, "stdout": str(warmup_stdout), "stderr": str(warmup_stderr)},
            "runs": samples,
            "medianSeconds": ordered[1],
        }

    measure("loc-only", loc_only)
    measure("syntax-only", syntax_only)
    measure("normal", config)

    profile = output / "normal.cprofile"
    profile_stdout = output / "normal.profile.json"
    profile_stderr = output / "normal.profile.stderr.txt"
    profile_command = [
        args.python, "-m", "cProfile", "-o", str(profile), "-m",
        "agent_code_guard.code_guard", ".", "--config", str(config), "--json", "--ci",
    ]
    profile_exit, _ = run_redirected(profile_command, target, profile_stdout, profile_stderr)
    if profile_exit != 0:
        raise RuntimeError(f"Normal profile failed with exit {profile_exit}.")
    metadata["profile"] = {
        "command": command_text(profile_command), "exitCode": profile_exit,
        "output": str(profile), "stdout": str(profile_stdout), "stderr": str(profile_stderr),
    }

    after = git_status(target, "post-run")
    metadata["targetStatusBefore"] = before
    metadata["targetStatusAfter"] = after
    metadata["normalAnalysisCreatedRepositoryMetadata"] = before != after
    results = output / "benchmark-results.json"
    write_json(results, metadata)
    if before != after:
        raise RuntimeError("Benchmark changed the target checkout; inspect benchmark-results.json.")
    print(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
