# Usage

## Current pre-release installation

Agent Code Guard is currently `0.1.0.dev0` and is not published to PyPI. Install
the current pre-release from a checkout, preferably as an isolated CLI tool:

```bash
git clone https://github.com/stef-k/agent-code-guard.git
cd agent-code-guard
pipx install .
```

Inside an activated Python virtual environment, use:

```bash
python -m pip install .
```

For repository development, an editable install is available:

```bash
python -m pip install -e .
```

`uv tool install .` is also a supported local-tool alternative. The checkout
runner at `skills/code-guard/scripts/code_guard.py` exists for repository and
skill compatibility; it is not the primary installed command.

## Command and scope

The public command is `code-guard`. With no paths, it defaults to `.`, but
normal development should select current work explicitly.

### Git changed-only

```bash
code-guard . --changed-only
```

This selects staged, unstaged, and untracked files known to the current Git
worktree, then intersects them with positional file or directory bounds.

### Staged changes

```bash
code-guard . --staged
```

This selects only index changes. Unstaged and untracked files are excluded.

### Base comparison

```bash
code-guard . --base-ref origin/main --ci
```

This selects added, copied, modified, or renamed files from the merge-base
comparison `<ref>...HEAD`. The ref must exist and resolve in the environment;
fetch the intended base before running in shallow or isolated CI checkouts.

Only one of `--changed-only`, `--staged`, and `--base-ref` may be used at a
time. Positional paths bound the Git-selected candidates; they do not add files
outside that selection.

### Explicit files and no VCS

Without Git, pass the exact files owned by the current change:

```bash
code-guard src/Foo.py src/Bar.ts docs/guide.md
```

Git selectors require a Git repository and fail rather than falling back to a
recursive audit. Do not create a manifest merely to provide scope.

### Deliberate recursive audit

```bash
code-guard .
```

A directory without a Git selector is a recursive audit. In a Git repository,
directory discovery respects Git tracking and ignore rules. Outside Git, it
walks the directory while pruning `.git`, `node_modules`, `bin`, and `obj`.
Changed work and a full audit are intentionally different operations.

### Symlinks

Recursive discovery does not follow symlinks. An explicitly supplied file
symlink expresses caller intent and is inspected at its resolved target. An
explicit directory symlink is rejected rather than traversed recursively.

Missing explicit paths, incompatible selectors, unavailable base refs, invalid
scope, and Git selectors outside a repository are tool errors. Git-derived
paths that no longer exist are ignored.

## Results and exit codes

- `PASS` means no special action and exits `0`.
- `REVIEW` means inspect findings and apply judgment; normal invocation exits `1`.
- `FAIL` blocks normal completion and exits `2`.
- Tool, configuration, parser/provider, or scope errors exit `3`.

`--ci` changes a REVIEW-only result to exit `0`. It does not suppress FAIL or
tool errors. REVIEW is not automatic refactoring, and metrics must never be
gamed.

## Human and JSON output

Human output is the default and emphasizes actionable findings. Add `--json`
for stable machine-readable output containing `overall`, per-guard results,
and `requiredPolicies`.

`requiredPolicies` lists the policy identifiers needed for actionable findings.
An agent should load only those referenced policies, preserve project intent,
and decide whether a REVIEW warrants meaningful improvement. A passing result
has no required policy work.

## Agent integration

CLI-only use needs no skill export. Installed distributions carry a
version-matched skill payload. Locate it with `code-guard --skill-path` or copy
it to an empty target with `code-guard --export-skill <target-directory>`.
See [Skill distribution](skill-distribution.md) for the complete contract.
