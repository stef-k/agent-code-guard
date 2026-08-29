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

## Legacy LOC adoption ratchet

Established repositories may adopt LOC policy without accepting further growth.
The default `guards.loc.ratchetAt: "fail"` records files above effective
`failAt`. Use `"review"` when existing files above effective `warnAt` may remain
but must not grow. Create the
canonical source-controlled ratchet over an intentionally bounded scope:

```bash
code-guard src/legacy --create-loc-baseline
git add .agent-tools/code-guard.loc-baseline.json
git diff --cached
```

The file is always
`<analysis-root>/.agent-tools/code-guard.loc-baseline.json`, where the root is
the enclosing Git top-level or, outside Git, the resolved invocation directory.
Normal analysis reads it automatically and never writes it. Under `fail`, a file
at its allowance, or reduced while still above `failAt`, becomes grandfathered
`REVIEW`. Under `review`, a file within its allowance keeps ordinary `REVIEW`
between `warnAt` and `failAt`, and is grandfathered only above `failAt`. Growth
above either allowance is `FAIL`. At or below the selected policy threshold,
the entry is reported as no longer needed.

After reducing or deleting legacy code, explicitly lower and prune entries:

```bash
code-guard src/legacy --update-loc-baseline
```

Update bounds come only from the positional paths. Update lowers existing
allowances, removes entries that are missing, excluded, inapplicable, or no
longer above the selected policy threshold, and leaves entries outside the bounds unchanged. It
never adds a newly oversized path or raises an allowance; any attempted growth
aborts the entire update. A rename is an old-path deletion plus a new,
ungrandfathered destination—Git history is not consulted. Manual JSON edits
are ordinary source-control changes and require review.

This ratchet differs from LOC exclusions, threshold overrides, and
`allowedLargeFiles`: exclusions skip LOC evaluation, overrides change ordinary
thresholds, and `allowedLargeFiles` is a reasoned static exemption without a
size-regression check. A ratchet entry may not overlap `allowedLargeFiles`.

This workflow is only for adopting established legacy repositories. New
projects, including Agent Code Guard itself, should meet policy directly and
must not create a ratchet baseline.

Do not switch between `fail` and `review`, raise thresholds, add exclusions or
exemptions, or edit allowances merely to silence a growth failure. Those are
source-controlled policy changes and require their own substantive justification.

## Results and exit codes

- `PASS` means no special action and exits `0`.
- `REVIEW` means inspect findings and apply judgment; normal invocation exits `1`.
- `FAIL` blocks normal completion and exits `2`.
- `INCOMPLETE` retains independent completed evidence when known per-file
  syntax/provider evidence is unavailable and exits `3`.
- Other tool, configuration, or scope errors exit `3` without a completed report.

`--ci` changes a REVIEW-only result to exit `0`. It does not suppress FAIL,
INCOMPLETE, or tool errors. REVIEW is not automatic refactoring, and metrics
must never be gamed.

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

When a known per-file syntax or provider failure occurs, the headline is
`INCOMPLETE`, followed by ordered unavailable context and the incomplete syntax
guard identifiers before ordinary findings. JSON uses `overall: "incomplete"`,
adds the authoritative completed aggregate as `completedOverall`, and includes
ordered top-level `unavailable` records containing `path`, embedded `language`,
`kind`, and the exact provider message. `scope.unavailable` overlaps
`analyzed`, so `analyzed + inapplicable == selected` remains true. Every guard
adds `complete` only on incomplete runs; incomplete syntax guards also add
ordered `unavailablePaths`. Guard states, findings, and `requiredPolicies`
continue to describe only completed evidence.

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

For incomplete output, full and debug retain identical unavailable records;
compact filters only ordinary passing findings and also retains those records
unchanged. All three JSON modes, human output, normal invocation, and `--ci`
exit `3`.

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

After a meaningful editing turn in Git, the normal structured agent command is:

```bash
code-guard . --changed-only --json --json-mode compact
```

Outside Git, pass the exact edited paths instead. An optional, user-authorized
platform hook may add `--ci`; this changes REVIEW's process exit from `1` to
`0` without hiding its findings or changing FAIL and tool-error exits.
Agent Code Guard does not install hooks.

See the [human and agent workflow](agent-workflow.md) for the repeated manual
and hook-assisted loop. Installed distributions also carry a version-matched
skill payload; [skill distribution](skill-distribution.md) documents discovery,
export, and platform activation.
## Performance benchmarking

Performance changes can be measured against the fixed Wayfarer workload with
`tools/benchmark-wayfarer.ps1`. The caller supplies a disposable checkout at
commit `679ddae9717bf78681a2cfbf794f687127b23b5d`, its exact project config, and
an output directory outside that checkout:

```powershell
.\tools\benchmark-wayfarer.ps1 `
  -WayfarerPath C:\bench\Wayfarer `
  -ConfigPath C:\bench\wayfarer-code-guard.config.json `
  -OutputDirectory C:\bench\results\after `
  -InstallationMode "editable wheel from issue 122 branch"
```

The script validates the source commit, records Python and Code Guard versions,
the configuration hash, exact commands, three fresh sequential warm-process
samples and medians for LOC-only, syntax-only, and normal six-guard scans, plus
a normal-run cProfile file. It compares complete Git status before and after the
run and fails if analysis creates repository metadata. It never clones or writes
to the target checkout and is intentionally not a CI test. Run the same script
and installation mode against the before and after revisions, retaining both
result directories for comparison.
