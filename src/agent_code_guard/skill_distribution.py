"""Locate and export the version-coupled Code Guard skill payload."""

from __future__ import annotations

from importlib.metadata import distribution, version
import json
from pathlib import Path
import shutil
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


PAYLOAD_FILES = (
    "SKILL.md",
    "LICENSE.txt",
    "agents/openai.yaml",
    "references/callable-size-policy.md",
    "references/complexity-policy.md",
    "references/loc-policy.md",
    "references/markdown-size-policy.md",
    "references/nesting-policy.md",
)


def skill_path() -> Path:
    """Return the installed canonical skill payload directory."""
    package = distribution("agent-code-guard")
    suffix = "share/agent-code-guard/skill/SKILL.md"
    path = next(
        (
            Path(package.locate_file(item)).parent
            for item in package.files or ()
            if str(item).replace("\\", "/").endswith(suffix)
        ),
        None,
    )
    if path is None:
        path = _editable_skill_path(package)
    if path is None:
        raise ValueError("installed distribution does not contain the Code Guard skill payload")
    _validate_payload(path)
    return path.resolve()


def export_skill(target: Path) -> Path:
    """Copy the installed payload into an empty caller-owned directory."""
    target = target.expanduser().resolve()
    if target.exists():
        if not target.is_dir():
            raise ValueError(f"skill export target is not a directory: {target}")
        if any(target.iterdir()):
            raise ValueError(f"skill export target is not empty: {target}")
    else:
        target.mkdir(parents=True)

    source_root = skill_path()
    for relative in PAYLOAD_FILES:
        source = source_root / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"installed skill payload has an unsafe or missing file: {relative}")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (target / ".agent-code-guard-version").write_text(
        f'{version("agent-code-guard")}\n', encoding="utf-8", newline="\n",
    )
    return target


def _validate_payload(path: Path) -> None:
    if not path.is_dir():
        raise ValueError(f"installed skill payload is missing: {path}")
    for relative in PAYLOAD_FILES:
        candidate = path / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError(f"installed skill payload has an unsafe or missing file: {relative}")


def _editable_skill_path(package) -> Path | None:
    """Use PEP 610 metadata when setuptools omits data-files from editable wheels."""
    direct_url = package.read_text("direct_url.json")
    if direct_url is None:
        return None
    metadata = json.loads(direct_url)
    if not metadata.get("dir_info", {}).get("editable"):
        return None
    parsed = urlparse(metadata.get("url", ""))
    if parsed.scheme != "file":
        return None
    checkout = Path(url2pathname(unquote(parsed.path)))
    return checkout / "skills" / "code-guard"
