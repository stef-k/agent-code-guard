"""Read the four fixed policy artifacts through retained runner-owned Git authority."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import subprocess

from . import callable_review_baseline, loc_baseline, markdown_baseline
from .guards import policy_relaxation
from .invocation import AnalysisContext, parse_configuration
from .result_model import GuardResult


def compare_current(
    context: AnalysisContext, loc_allowances, markdown_allowances, callable_reviews,
) -> GuardResult:
    """Compare the already loaded working-tree inputs; never reread HEAD or config."""
    if context.git_authority is None or context.configuration_path is None:
        raise ValueError('policy comparison requires runner-owned Git and active configuration authority')
    artifact = _owned_configuration_path(context.configuration_path, context.root)
    # All three current baselines share this directory, even when artifacts are
    # absent. This extra ownership check applies only to Git policy comparison.
    loc_baseline.validate_storage_path(context.root)
    base = context.git_authority.base_object
    text = read_artifact(context.root, base, artifact)
    document = parse_configuration(text) if text is not None else {}
    allowances = []
    for baseline in (loc_baseline, markdown_baseline, callable_review_baseline):
        text = read_artifact(context.root, base, baseline.RELATIVE_PATH)
        allowances.append(baseline.parse(text) if text is not None else {})
    before = policy_relaxation.effective_policy(document, *allowances)
    after = policy_relaxation.effective_policy(context.configuration, loc_allowances, markdown_allowances, callable_reviews)
    # The historical allowance/config relationship is structural, independent of today's files.
    loc_baseline.validate_overlap(before.loc_allowances, before.loc)
    return policy_relaxation.compare(artifact, before, after)


def _owned_configuration_path(path: Path, root: Path) -> str:
    """Canonicalize caller aliases while rejecting ambiguous repository ownership."""
    try:
        relative = path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError('active configuration is outside the Git repository; policy comparison is unavailable') from exc
    # Preserve link identity before canonical aliases erase it. System ancestors outside
    # the repository (for example macOS /var) do not own a repository policy path.
    for candidate in (path, *path.parents):
        if candidate.is_symlink() and (
            candidate.parent.resolve().is_relative_to(root) or candidate.resolve().is_relative_to(root)
        ):
            raise ValueError('active configuration must not traverse a repository policy symlink')
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        if current.is_symlink() or (index < len(relative.parts) - 1 and current.exists() and not current.is_dir()):
            raise ValueError('active configuration must use real directory ancestors inside the Git repository')
    return relative.as_posix()


def read_artifact(root: Path, base: str | None, relative: str) -> str | None:
    """Look up exact ancestor/tree entries and one blob, without history discovery."""
    if base is None:
        return None
    parts = PurePosixPath(relative).parts
    for index in range(1, len(parts) + 1):
        prefix = '/'.join(parts[:index])
        result = subprocess.run(
            ['git', 'ls-tree', '-z', base, '--', f':(literal){prefix}'],
            cwd=root, check=True, capture_output=True,
        )
        entries = [entry for entry in result.stdout.split(b'\0') if entry]
        if not entries:
            return None
        metadata, stored_path = entries[0].split(b'\t', 1)
        mode, kind, object_id = metadata.decode('ascii').split()
        if len(entries) != 1 or stored_path.decode('utf-8') != prefix:
            raise ValueError(f'non-exact historical policy lookup: {relative}')
        ancestor = index < len(parts)
        if (ancestor and (mode != '040000' or kind != 'tree')) or (
            not ancestor and (mode not in {'100644', '100755'} or kind != 'blob')
        ):
            raise ValueError(f'unsafe historical policy object or non-directory ancestor: {prefix}')
    blob = subprocess.run(['git', 'cat-file', 'blob', object_id], cwd=root, check=True, capture_output=True)
    return blob.stdout.decode('utf-8')
