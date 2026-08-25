# Usage

## Installation

Install Agent Code Guard as an isolated CLI tool with pipx:

```bash
pipx install agent-code-guard
```

Inside an activated Python virtual environment, use:

```bash
python -m pip install agent-code-guard
```

An isolated uv tool installation is also available:

```bash
uv tool install agent-code-guard
```

For source or repository development installs, run one of the following from a
checkout:

```bash
python -m pip install .
python -m pip install -e .
```

The checkout runner at `skills/code-guard/scripts/code_guard.py` exists for
repository and skill compatibility; it is not the primary installed command.

## Command and scope

The public command is `code-guard`. With no paths, it defaults to `.`, but
normal development should select current work explicitly.

### Installed version

Report the installed distribution identity without configuration, scope, Git,
provider, skill, or guard work:

```text
$ code-guard --version
agent-code-guard <version>
```

For machine-readable output:

```text
$ code-guard --version --json
{
  "distribution": "agent-code-guard",
  "version": "<version>"
}
```

The value is read from installed metadata for the canonical
`agent-code-guard` distribution. `--version` may be combined only with
`--json`. Both successful version forms exit `0`; incompatible arguments or
unavailable metadata exit `3`. Human errors use standard error and JSON errors
use an `error` object on standard output. If distribution metadata is
unavailable, the error is
`installed distribution metadata is unavailable for agent-code-guard`.

### Installation diagnostics

Inspect the active installation and its immediate local capabilities without
running project analysis:

```bash
code-guard doctor
code-guard doctor --json
```

The human and JSON reports cover the active distribution, Python process,
invoked entry point, bundled skill, current-directory configuration and Git
context, and all supported parser providers. A healthy report exits `0`; a
completed unhealthy report exits `1`; invocation or internal failures that
prevent a report exit `3`. Completed reports use standard output only.

`doctor` is reserved only as the exact first token. Analyze a file or directory
with that name through a qualified spelling such as `./doctor`, `.\doctor`, or
an absolute path. Doctor is read-only: it does not analyze source, repair or
install dependencies, export skills, modify configuration or Git state, access
the network, or persist diagnostics.

Diagnostic output includes resolved launcher, interpreter, skill, Git, and
configuration paths. Treat those paths and other environment details as
potentially sensitive before sharing a report.

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

Human output is the default and emphasizes actionable findings. Every completed
analysis starts with the aggregate state and exact scope counts:

```text
PASS: 3 selected; 2 analyzed; 1 inapplicable; 0 excluded.
```

The labels do not pluralize. An empty valid selection is
`PASS: 0 selected; 0 analyzed; 0 inapplicable; 0 excluded.` and exits `0`.
Existing finding and required-policy lines follow this summary unchanged.

The counts have these meanings:

- `selected`: files remaining after discovery, bounds, normalization,
  deduplication, absent Git-derived entries, and all-guard exclusions;
- `analyzed`: selected files applicable to at least one enabled guard;
- `inapplicable`: selected files applicable to no enabled guard;
- `excluded`: existing normalized files removed specifically by
  `scope.exclude` or `--scope-exclude`.

Therefore `analyzed + inapplicable == selected`, and an excluded file belongs
to none of the other sets. All values are non-negative integers. Git-ignored
files never discovered, paths outside positional bounds, and absent Git-derived
files are not counted as exclusions.

Add `--json` for the stable, compatible full machine-readable output, including
all passing and actionable findings. Completed `PASS`, `REVIEW`, and `FAIL`
results include exactly one top-level summary alongside the existing `overall`,
`requiredPolicies`, and `guards` values:

```json
"scope": {
  "selected": 3,
  "analyzed": 2,
  "inapplicable": 1,
  "excluded": 0
}
```

Counts do not change aggregate state, findings, required policies, or exit
codes. Tool errors retain their existing human or JSON error form and do not
include a successful `scope` object.

Choose a completed-analysis serialization mode explicitly when needed:

```bash
code-guard . --json --json-mode compact
code-guard . --json --json-mode debug
```

`compact` is intended for routine agent checks. It preserves `overall`, the
complete `scope`, `requiredPolicies`, every guard and guard state, and existing
guard and retained-finding ordering. It omits each finding whose normalized
state is `pass` and retains unchanged findings whose state is `review` or
`fail`. This includes omitting LOC exemptions: their native status is `exempt`,
but their normalized state is `pass`. `debug` is an explicit name for the full
output and is byte-for-byte identical to bare `--json` for the same completed
analysis.

Both named modes require `--json` and apply only to completed analysis output.
They do not change analysis, scope, policies, ordering, aggregate or guard
states, exit codes, or error shapes and channels. Version JSON supports only
bare `--version --json`; skill-management modes are also incompatible with JSON
analysis options. Values are exact and case-sensitive. There is no detail mode.

`requiredPolicies` lists the policy identifiers needed for actionable findings.
An agent should load only those referenced policies, preserve project intent,
and decide whether a REVIEW warrants meaningful improvement. A passing result
has no required policy work.

## Agent integration

CLI-only use needs no skill export. Installed distributions carry a
version-matched skill payload. Locate it with `code-guard --skill-path` or copy
it to an empty target with `code-guard --export-skill <target-directory>`.
See [Skill distribution](skill-distribution.md) for the complete contract.
