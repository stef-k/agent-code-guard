"""Read-only diagnostics for the active Code Guard process and working directory."""

from __future__ import annotations

import argparse
from importlib import metadata
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .analysis.provider import TreeSitterProvider
from .config_validation import validate_configuration
from .guards import callable_size, complexity, loc, markdown_document_size, markdown_section_size, nesting
from .skill_distribution import skill_path as installed_skill_path

DISTRIBUTION_NAME = "agent-code-guard"
ENTRY_POINT_TARGET = "agent_code_guard.code_guard:main"
PROVIDER_DISTRIBUTIONS = ("tree-sitter", "tree-sitter-language-pack")
PROVIDER_LANGUAGES = (
    "python", "go", "kotlin", "csharp", "java", "javascript", "typescript",
    "tsx", "cpp", "rust", "php", "swift", "dart", "vue",
)


def _failure(message: str, status: str = "unavailable") -> dict[str, object]:
    return {"status": status, "message": message}


def _distribution() -> tuple[dict[str, object], object | None]:
    try:
        package = metadata.distribution(DISTRIBUTION_NAME)
        installed_version = package.version
        if not isinstance(installed_version, str):
            raise TypeError
        return {
            "name": DISTRIBUTION_NAME, "version": installed_version,
            "status": "ok", "message": None,
        }, package
    except Exception:
        return {
            "name": DISTRIBUTION_NAME, "version": None,
            **_failure(f"installed distribution metadata is unavailable for {DISTRIBUTION_NAME}"),
        }, None


def _python() -> dict[str, object]:
    try:
        return {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": str(Path(sys.executable).resolve()),
            "status": "ok", "message": None,
        }
    except Exception:
        return {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": str(sys.executable),
            **_failure("running Python executable could not be resolved"),
        }


def _entry_point(package: object | None) -> dict[str, object]:
    invoked = sys.argv[0]
    resolved = None
    try:
        candidate = Path(invoked)
        if candidate.exists():
            resolved = candidate.resolve()
    except (OSError, RuntimeError):
        pass

    kind = "other"
    if resolved is not None:
        normalized = resolved.as_posix().lower()
        if normalized.endswith("/skills/code-guard/scripts/code_guard.py"):
            kind = "checkout-compatibility-runner"
        elif resolved.stem.lower() in {"code-guard", "code_guard"}:
            kind = "console-script"

    owns_entry_point = False
    if package is not None:
        try:
            owns_entry_point = any(
                point.group == "console_scripts"
                and point.name == "code-guard"
                and point.value == ENTRY_POINT_TARGET
                for point in package.entry_points
            )
        except Exception:
            owns_entry_point = False

    status = "ok"
    message = None
    if not owns_entry_point:
        status = "unavailable"
        message = "active distribution does not declare the expected code-guard entry point"
    elif resolved is None:
        status = "unavailable"
        message = "invoked launcher could not be resolved directly"
    elif kind == "other":
        status = "unavailable"
        message = "invoked launcher is not a recognized Code Guard launcher"
    return {
        "name": "code-guard", "target": ENTRY_POINT_TARGET, "invoked": invoked,
        "resolvedPath": str(resolved) if resolved is not None else None,
        "kind": kind, "status": status, "message": message,
    }


def _skill() -> dict[str, object]:
    try:
        path = installed_skill_path()
        return {"available": True, "path": str(path.resolve()), "status": "ok", "message": None}
    except Exception:
        return {
            "available": False, "path": None,
            **_failure("bundled Code Guard skill payload is unavailable or invalid"),
        }


def _configuration(cwd: Path) -> dict[str, object]:
    path = cwd / ".agent-tools" / "code-guard.config.json"
    try:
        exists = path.exists()
    except (OSError, RuntimeError):
        return {
            "mode": "file", "path": str(path.absolute()), "valid": False,
            **_failure("configuration file could not be inspected"),
        }
    if not exists:
        return {"mode": "defaults", "path": None, "valid": True, "status": "ok", "message": None}
    resolved = path.resolve()
    args = argparse.Namespace(
        config=str(resolved), warn=None, fail=None, include=[], exclude=[],
        count_blank_lines=False, ignore_comment_lines=False,
    )
    try:
        validate_configuration(str(resolved), cwd)
        for loader in (
            loc.load_config, callable_size.load_config, nesting.load_config,
            complexity.load_config, markdown_document_size.load_config,
            markdown_section_size.load_config,
        ):
            loader(args)
        return {"mode": "file", "path": str(resolved), "valid": True, "status": "ok", "message": None}
    except (OSError, UnicodeError):
        return {
            "mode": "file", "path": str(resolved), "valid": False,
            **_failure("configuration file could not be read"),
        }
    except Exception:
        return {
            "mode": "file", "path": str(resolved), "valid": False,
            **_failure("configuration file is malformed or unsupported", "invalid"),
        }


def _git(cwd: Path) -> dict[str, object]:
    executable = shutil.which("git")
    if executable is None:
        return {
            "executableAvailable": False, "executable": None,
            "repositoryAvailable": False, "root": None,
            **_failure("Git executable is unavailable"),
        }
    resolved_executable = str(Path(executable).resolve())
    try:
        result = subprocess.run(
            [executable, "rev-parse", "--show-toplevel"], cwd=cwd,
            text=True, capture_output=True, check=False,
        )
    except Exception:
        return {
            "executableAvailable": True, "executable": resolved_executable,
            "repositoryAvailable": False, "root": None,
            **_failure("Git repository detection failed"),
        }
    if result.returncode != 0:
        return {
            "executableAvailable": True, "executable": resolved_executable,
            "repositoryAvailable": False, "root": None,
            **_failure("current directory is not in a Git repository"),
        }
    try:
        root = str(Path(result.stdout.strip()).resolve())
    except Exception:
        return {
            "executableAvailable": True, "executable": resolved_executable,
            "repositoryAvailable": False, "root": None,
            **_failure("Git repository root could not be resolved"),
        }
    return {
        "executableAvailable": True, "executable": resolved_executable,
        "repositoryAvailable": True, "root": root, "status": "ok", "message": None,
    }


def _providers() -> dict[str, object]:
    distributions = []
    failed_distributions = []
    for name in PROVIDER_DISTRIBUTIONS:
        try:
            installed_version = metadata.version(name)
            if not isinstance(installed_version, str):
                raise TypeError
            distributions.append({"name": name, "version": installed_version, "status": "ok", "message": None})
        except Exception:
            failed_distributions.append(name)
            distributions.append({
                "name": name, "version": None,
                **_failure(f"installed distribution metadata is unavailable for {name}"),
            })

    languages = []
    failed_languages = []
    try:
        provider = TreeSitterProvider()
    except Exception:
        provider = None
    for language in PROVIDER_LANGUAGES:
        try:
            if provider is None:
                raise RuntimeError
            provider.parse(language, b"")
            languages.append({"name": language, "status": "ok", "message": None})
        except Exception:
            failed_languages.append(language)
            languages.append({
                "name": language,
                **_failure(f"syntax provider is unavailable for {language}"),
            })
    failed = [*failed_distributions, *failed_languages]
    return {
        "status": "ok" if not failed else "unavailable",
        "message": None if not failed else f"provider checks unavailable: {', '.join(failed)}",
        "distributions": distributions,
        "languages": languages,
    }


def gather_report() -> dict[str, object]:
    """Gather all independent diagnostics without invoking ordinary analysis."""
    cwd = Path.cwd()
    distribution, package = _distribution()
    python = _python()
    entry_point = _entry_point(package)
    skill = _skill()
    configuration = _configuration(cwd)
    git = _git(cwd)
    providers = _providers()
    required = (distribution, python, entry_point, skill, configuration, providers)
    status = "healthy" if all(item["status"] == "ok" for item in required) else "unhealthy"
    return {
        "schemaVersion": 1,
        "status": status,
        "distribution": distribution,
        "python": python,
        "entryPoint": entry_point,
        "skill": skill,
        "configuration": configuration,
        "git": git,
        "providers": providers,
    }


def _label(item: dict[str, object]) -> str:
    return str(item["status"]).upper()


def _suffix(item: dict[str, object]) -> str:
    return "" if item["status"] == "ok" else f" - {item['message']}"


def format_human(report: dict[str, object]) -> str:
    distribution = report["distribution"]
    python = report["python"]
    entry = report["entryPoint"]
    skill = report["skill"]
    configuration = report["configuration"]
    git = report["git"]
    providers = report["providers"]
    config_fact = (
        "defaults (no configuration file)"
        if configuration["mode"] == "defaults"
        else f"file {configuration['path']}"
    )
    git_fact = (
        f"{git['executable']}; repository {git['root']}"
        if git["repositoryAvailable"]
        else f"{git['executable'] or 'no Git executable'}; no repository"
    )
    provider_versions = "; ".join(
        f"{item['name']} {item['version'] if item['version'] is not None else 'unavailable'}"
        for item in providers["distributions"]
    )
    available_languages = sum(item["status"] == "ok" for item in providers["languages"])
    return "\n".join((
        f"Code Guard doctor: {str(report['status']).upper()}",
        f"Distribution: {_label(distribution)} {distribution['name']} {distribution['version'] if distribution['version'] is not None else 'unavailable'}{_suffix(distribution)}",
        f"Python: {_label(python)} {python['implementation']} {python['version']} ({python['executable']}){_suffix(python)}",
        f"Entry point: {_label(entry)} {entry['name']} -> {entry['target']} ({entry['kind']}; {entry['resolvedPath'] or 'unresolved'}){_suffix(entry)}",
        f"Skill: {_label(skill)} {skill['path'] or 'unavailable'}{_suffix(skill)}",
        f"Configuration: {_label(configuration)} {config_fact}{_suffix(configuration)}",
        f"Git: {_label(git)} {git_fact}{_suffix(git)}",
        f"Providers: {_label(providers)} {provider_versions}; {available_languages}/{len(providers['languages'])} languages available{_suffix(providers)}",
    ))
