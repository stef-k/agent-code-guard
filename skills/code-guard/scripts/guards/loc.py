"""Canonical LOC guard, migrated from Agent LOC Guard commit 75ab39d."""

from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from file_selection import collect_candidates
from result_model import Finding, GuardResult

DEFAULT_WARN_AT = 400
DEFAULT_FAIL_AT = 600
DEFAULT_INCLUDE_EXTENSIONS = {
    ".cs", ".cshtml", ".razor", ".js", ".jsx", ".ts", ".tsx", ".py", ".java",
    ".kt", ".kts", ".scala", ".go", ".rs", ".swift", ".dart", ".zig", ".cpp",
    ".c", ".h", ".hpp", ".m", ".mm", ".fs", ".fsx", ".vb", ".css", ".scss",
    ".html", ".vue", ".php", ".rb", ".ex", ".exs", ".erl", ".hrl", ".clj",
    ".cljs", ".cljc", ".lua", ".sql", ".sh", ".ps1",
}
DEFAULT_EXCLUDES = [
    "**/.git/**", "**/.vs/**", "**/.idea/**", "**/.vscode/**", "**/bin/**", "**/obj/**",
    "**/node_modules/**", "**/dist/**", "**/build/**", "**/coverage/**", "**/generated/**",
    "**/Generated/**", "**/vendor/**", "**/Vendor/**", "**/Migrations/**", "**/*.g.cs",
    "**/*.generated.cs", "**/*.Designer.cs", "**/*.designer.cs", "**/*.min.js", "**/*.min.css",
]
COMMENT_PREFIXES = {
    ".cs": ["//"], ".cshtml": ["@*"], ".razor": ["@*", "//"], ".js": ["//"],
    ".jsx": ["//"], ".ts": ["//"], ".tsx": ["//"], ".py": ["#"], ".java": ["//"],
    ".kt": ["//"], ".kts": ["//"], ".scala": ["//"], ".go": ["//"], ".rs": ["//"],
    ".swift": ["//"], ".dart": ["//"], ".zig": ["//"], ".cpp": ["//"], ".c": ["//"],
    ".h": ["//"], ".hpp": ["//"], ".m": ["//"], ".mm": ["//"], ".fs": ["//"],
    ".fsx": ["//"], ".vb": ["'"], ".css": ["/*"], ".scss": ["//", "/*"],
    ".html": ["<!--"], ".vue": ["<!--"], ".php": ["//", "#"], ".rb": ["#"],
    ".ex": ["#"], ".exs": ["#"], ".erl": ["%"], ".hrl": ["%"], ".clj": [";"],
    ".cljs": [";"], ".cljc": [";"], ".lua": ["--"], ".sql": ["--"], ".sh": ["#"],
    ".ps1": ["#"],
}


@dataclass(frozen=True)
class AllowedLargeFile:
    path: str
    reason: str


@dataclass(frozen=True)
class ThresholdOverride:
    match: list[str]
    warn_at: int
    fail_at: int


@dataclass(frozen=True)
class Config:
    enabled: bool
    warn_at: int
    fail_at: int
    count_blank_lines: bool
    count_comment_lines: bool
    include_extensions: set[str]
    exclude: list[str]
    allowed_large_files: list[AllowedLargeFile]
    overrides: list[ThresholdOverride]


def load_config(args: argparse.Namespace) -> Config:
    document: dict[str, Any] = {}
    config_path = args.config
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"config file not found: {config_path}")
        document = json.loads(path.read_text(encoding="utf-8"))
    else:
        auto = Path(".agent-tools/code-guard.config.json")
        if auto.exists():
            document = json.loads(auto.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("configuration must be an object")
    guards = document.get("guards", {})
    if not isinstance(guards, dict):
        raise ValueError("guards must be an object")
    data = guards.get("loc", {})
    if not isinstance(data, dict):
        raise ValueError("guards.loc must be an object")
    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("guards.loc.enabled must be a boolean")

    warn_at = args.warn if args.warn is not None else data.get("warnAt", DEFAULT_WARN_AT)
    fail_at = args.fail if args.fail is not None else data.get("failAt", DEFAULT_FAIL_AT)
    warn_at = parse_positive_integer(warn_at, "guards.loc.warnAt")
    fail_at = parse_positive_integer(fail_at, "guards.loc.failAt")
    if warn_at >= fail_at:
        raise ValueError("guards.loc.warnAt must be lower than guards.loc.failAt")
    extensions = data.get("includeExtensions", list(DEFAULT_INCLUDE_EXTENSIONS))
    if not isinstance(extensions, list) or any(not isinstance(value, str) for value in extensions):
        raise ValueError("guards.loc.includeExtensions must be an array of strings")
    include_extensions = {normalise_extension(value) for value in extensions}
    include_extensions.update(normalise_extension(value) for value in args.include)
    exclude = data.get("exclude", DEFAULT_EXCLUDES)
    if not isinstance(exclude, list) or any(not isinstance(value, str) for value in exclude):
        raise ValueError("guards.loc.exclude must be an array of strings")
    exclude = list(exclude) + args.exclude
    count_blank = data.get("countBlankLines", False)
    count_comments = data.get("countCommentLines", True)
    if not isinstance(count_blank, bool) or not isinstance(count_comments, bool):
        raise ValueError("guards.loc line-count options must be booleans")
    return Config(
        enabled, warn_at, fail_at, count_blank or args.count_blank_lines,
        False if args.ignore_comment_lines else count_comments, include_extensions, exclude,
        parse_allowed_large_files(data.get("allowedLargeFiles", [])),
        parse_overrides(data.get("overrides", [])),
    )


def parse_allowed_large_files(value: Any) -> list[AllowedLargeFile]:
    if not isinstance(value, list):
        raise ValueError("guards.loc.allowedLargeFiles must be an array")
    allowed = []
    for index, item in enumerate(value):
        location = f"guards.loc.allowedLargeFiles[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{location} must be an object")
        path = item.get("path")
        reason = item.get("reason")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"{location}.path must be a non-empty string")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{location}.reason must be a non-empty string")
        allowed.append(AllowedLargeFile(path.replace("\\", "/"), reason))
    return allowed


def parse_overrides(value: Any) -> list[ThresholdOverride]:
    if not isinstance(value, list):
        raise ValueError("guards.loc.overrides must be an array")
    overrides = []
    for index, item in enumerate(value):
        location = f"guards.loc.overrides[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{location} must be an object")
        patterns = item.get("match")
        if not isinstance(patterns, list) or not patterns or any(
            not isinstance(pattern, str) or not pattern.strip() for pattern in patterns
        ):
            raise ValueError(f"{location}.match must be a non-empty array of non-empty strings")
        warn_at = parse_positive_integer(item.get("warnAt"), f"{location}.warnAt")
        fail_at = parse_positive_integer(item.get("failAt"), f"{location}.failAt")
        if warn_at >= fail_at:
            raise ValueError(f"{location}.warnAt must be lower than {location}.failAt")
        overrides.append(ThresholdOverride([pattern.replace("\\", "/") for pattern in patterns], warn_at, fail_at))
    return overrides


def parse_positive_integer(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{location} must be a positive integer")
    return value


def normalise_extension(value: str) -> str:
    value = value.strip()
    return value if not value or value.startswith(".") else f".{value}"


def run(args: argparse.Namespace, root: Path, config: Config) -> GuardResult:
    if not config.enabled:
        return GuardResult("loc", "pass", [])
    files = []
    for candidate in collect_candidates(args, root):
        resolved = candidate if candidate.is_absolute() else Path.cwd() / candidate
        resolved = resolved.resolve()
        if resolved.exists() and resolved.is_file() and should_include(resolved, config, root):
            files.append(resolved)
    findings = [evaluate(path, config, root) for path in sorted(set(files), key=lambda p: relative_path(p, root))]
    state = "fail" if any(item.state == "fail" for item in findings) else (
        "review" if any(item.state == "review" for item in findings) else "pass"
    )
    return GuardResult("loc", state, findings)


def should_include(path: Path, config: Config, root: Path) -> bool:
    return path.suffix in config.include_extensions and not any(
        matches_path_glob(relative_path(path, root), pattern) for pattern in config.exclude
    )


def matches_path_glob(path: str, pattern: str) -> bool:
    normalised_path = path.replace("\\", "/").removeprefix("./")
    normalised_pattern = pattern.replace("\\", "/").removeprefix("./")
    if normalised_path == normalised_pattern:
        return True
    candidates = [normalised_pattern]
    while normalised_pattern.startswith("**/"):
        normalised_pattern = normalised_pattern[3:]
        candidates.append(normalised_pattern)
    return any(fnmatch.fnmatch(normalised_path, candidate) for candidate in candidates)


def evaluate(path: Path, config: Config, root: Path) -> Finding:
    rel = relative_path(path, root)
    counted = count_loc(path, config)
    warn_at, fail_at, override_index = effective_thresholds(rel, config)
    allowed = next((item for item in config.allowed_large_files if matches_path_glob(rel, item.path)), None)
    if allowed and counted > warn_at:
        native_status, state, reason = "exempt", "pass", allowed.reason
    elif counted > fail_at:
        native_status, state, reason = "fail", "fail", None
    elif counted > warn_at:
        native_status, state, reason = "warn", "review", None
    else:
        native_status, state, reason = "ok", "pass", None
    return Finding(rel, state, native_status, counted, warn_at, fail_at, override_index, reason)


def count_loc(path: Path, config: Config) -> int:
    count = 0
    prefixes = COMMENT_PREFIXES.get(path.suffix, [])
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            stripped = raw_line.rstrip("\n\r").strip()
            if not config.count_blank_lines and not stripped:
                continue
            if not config.count_comment_lines and is_simple_comment_line(stripped, prefixes, path.suffix):
                continue
            count += 1
    return count


def is_simple_comment_line(stripped: str, prefixes: list[str], extension: str) -> bool:
    if not stripped or (extension == ".php" and stripped.startswith("#[")):
        return False
    return any(stripped.startswith(prefix) for prefix in prefixes)


def effective_thresholds(rel: str, config: Config) -> tuple[int, int, int | None]:
    selected = None
    for index, override in enumerate(config.overrides):
        if any(matches_path_glob(rel, pattern) for pattern in override.match):
            selected = (index, override)
    if selected is None:
        return config.warn_at, config.fail_at, None
    index, override = selected
    return override.warn_at, override.fail_at, index


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
