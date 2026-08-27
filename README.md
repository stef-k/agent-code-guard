# Agent Code Guard

<p align="center">
  <img src="https://raw.githubusercontent.com/stef-k/agent-code-guard/main/assets/agent-code-guard-mark.svg" width="180" alt="Agent Code Guard project mark">
</p>

Deterministic maintainability guardrails for source code and Markdown changed by
a human or coding agent.

[![Production Analysis](https://github.com/stef-k/agent-code-guard/actions/workflows/analysis.yml/badge.svg)](https://github.com/stef-k/agent-code-guard/actions/workflows/analysis.yml)
[![PyPI](https://img.shields.io/pypi/v/agent-code-guard?logo=pypi&logoColor=white)](https://pypi.org/project/agent-code-guard/)
[![Python 3.10–3.14](https://img.shields.io/badge/Python-3.10%E2%80%933.14-3776AB?logo=python&logoColor=white)](https://github.com/stef-k/agent-code-guard/blob/main/docs/platform-support.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/stef-k/agent-code-guard/blob/main/LICENSE)

Agent Code Guard measures file size, callable size, structural nesting,
cyclomatic complexity, Markdown document size, and Markdown section size. It
reports deterministic **PASS**, **REVIEW**, or **FAIL** results without
rewriting your files.

It complements rather than replaces tests, compilers, linters, formatters,
security tools, and design judgment.

## Why it is useful

Code Guard surfaces files and callables that are becoming difficult to review,
deep nesting and complex decision logic, and Markdown specifications that are
losing navigability. It gives humans and agents the same repeatable review
point after edits and can prevent silent LOC growth beyond an explicit project
policy.

### What humans gain

- Consistent signals across supported languages and Markdown, whether a change
  came from a person or an agent.
- A shared PASS/REVIEW/FAIL vocabulary: continue, inspect with judgment, or
  block pending correction or an authorized exception.
- The same checks locally and in CI, with no configuration required for
  ordinary use and no automatic source mutation.

### What agents gain

- Deterministic feedback after edits and consistent process exits.
- Changed-file scope instead of unnecessary full-repository scans.
- Compact JSON that omits normalized pass noise while retaining actionable
  findings and result structure.
- Named required policies, so only relevant guidance needs to be loaded, plus a
  version-matched bundled skill with REVIEW-judgment and anti-gaming rules.

This workflow is designed to reduce unnecessary output and policy loading. It
still requires the source context needed to understand and judge each finding;
it makes no claim about measured token savings.

## Installation

[pipx](https://pipx.pypa.io/) isolates the command from project environments:

```bash
pipx install agent-code-guard
code-guard --version
code-guard doctor
```

`--version` confirms the installed distribution identity. `doctor` checks the
active installation's health. See the [usage guide](https://github.com/stef-k/agent-code-guard/blob/main/docs/usage.md) for virtual
environment, uv, and developer alternatives.

### Ask your agent to adopt it

Copy this prompt to a coding agent:

> Consult the official Agent Code Guard repository and documentation. Install
> the published distribution in an isolated supported way, preferably with
> pipx; verify `code-guard --version` and run `code-guard doctor`. Locate the
> installed version-matched skill with `code-guard --skill-path`, and use or
> export only that skill through the documented mechanism. Inspect this
> repository without creating a LOC baseline and use changed-work scope. Ask
> before exporting into a persistent skill directory or configuring hooks.
> Never weaken thresholds, exclusions, configuration, or baselines merely to
> silence findings.

## Five-minute start

From a Git worktree, inspect the current change:

```bash
code-guard . --changed-only
```

Git supplies the changed candidates; every enabled and applicable guard runs.
No configuration is needed. A REVIEW asks for inspection and judgment, not an
automatic refactor. Outside Git, pass the exact edited files instead, such as
`code-guard src/app.py docs/guide.md`.

See the [agent workflow guide](https://github.com/stef-k/agent-code-guard/blob/main/docs/agent-workflow.md) for repeated human and
agent use.

## Recommended workflow

```text
edit supported code or Markdown
        ↓
run Code Guard on changed scope
        ↓
PASS → continue
REVIEW → inspect, justify or genuinely improve
FAIL → fix or obtain an explicitly authorized exception
        ↓
rerun
        ↓
report the result before completion
```

Use `code-guard . --changed-only --json --json-mode compact` for a structured,
low-noise manual agent check. Hooks are optional, platform-owned, and require
user authorization; Code Guard does not install them. The
[workflow guide](https://github.com/stef-k/agent-code-guard/blob/main/docs/agent-workflow.md) owns the complete manual and
hook-assisted process.

## Interpreting results

- **PASS** — no special action; exit `0`.
- **REVIEW** — inspect and decide whether genuine structural improvement is
  warranted; normally exit `1`.
- **FAIL** — blocks normal completion until fixed or an explicitly authorized
  exception applies; exit `2`.
- A tool, invocation, configuration, scope, or provider error exits `3`.

`--ci` makes REVIEW nonblocking at the process level by changing its exit to
`0`; it does not hide the findings or change FAIL and tool-error exits.

**Never game a metric.** Do not create artificial helpers, files,
abstractions, formatting, exclusions, or policy changes merely to lower a
measurement. A REVIEW is not proof of a defect or a mandatory refactor.

## Guard reference

| Guard | Default |
| --- | --- |
| File LOC | REVIEW >400, FAIL >600 |
| Callable size | REVIEW >80 physical LOC |
| Structural nesting | REVIEW >4 |
| Cyclomatic complexity | REVIEW >15 |
| Markdown document size | REVIEW >800 physical lines |
| Markdown direct-section size | REVIEW >200 physical lines |

Comparisons are strictly greater-than, so equality passes. All guards except
file LOC are REVIEW-only; only file LOC can FAIL. A new guard must provide
distinct, deterministic value rather than duplicate conventional tooling. See
[Guard admission](https://github.com/stef-k/agent-code-guard/blob/main/docs/guard-admission.md).

### Result and JSON reference

Every completed analysis reports selected, analyzed, inapplicable, and
all-guard-excluded file counts. Bare `--json` is the compatible full output;
`--json-mode debug` is byte-identical for the same completed invocation, while
`--json-mode compact` removes only normalized `pass` findings and retains the
result, scope, required policies, guards, ordering, and actionable findings.
Named modes require `--json`. See [Usage](https://github.com/stef-k/agent-code-guard/blob/main/docs/usage.md) for the schema and
option contract.

### Common scope commands

```bash
# Current Git work
code-guard . --changed-only

# Pull request or branch comparison
code-guard . --base-ref origin/main --ci

# Deliberate full audit
code-guard .
```

The base ref must exist in the chosen environment. Changed work is not a full
audit; do not repeatedly scan unrelated files after every edit.

### Supported languages and formats

Syntax guards support Python, Go, Kotlin, C#, Java, JavaScript, TypeScript, JSX,
TSX, Vue JavaScript/TypeScript script regions, C++, Rust, PHP, Swift, and Dart.
Markdown guards apply to `.md` files.

Generic `.h` files are not syntax-dispatched; `.markdown` is not enabled; Vue
template and style regions are not executable syntax input; and unsupported
artifacts are inapplicable. Malformed applicable syntax or a required provider
failure is a fail-closed tool error. See [Language support](https://github.com/stef-k/agent-code-guard/blob/main/docs/language-support.md).

### Skill integration

An installed distribution includes the matching Code Guard skill payload:

```bash
code-guard --skill-path
code-guard --export-skill <target-directory>
```

Skill activation is platform-specific and is not performed by pipx or Code
Guard. See [Skill distribution](https://github.com/stef-k/agent-code-guard/blob/main/docs/skill-distribution.md). The checkout
compatibility runner is for repository development, not normal installation.

### Configuration

Built-in defaults require no configuration. Configure a project only for a
concrete policy reason; see the [configuration guide](https://github.com/stef-k/agent-code-guard/blob/main/docs/configuration.md).
The LOC baseline is an explicit adoption tool for established legacy
repositories, not an ordinary-use requirement or a way to silence findings.

## Trust, CI, and platform support

CI installs Agent Code Guard and analyzes its own real checkout. REVIEW findings
remain visible but non-blocking, while FAIL findings and tool errors block the
workflow; the repository intentionally uses no LOC baseline.

The maintained interpreter range is **CPython 3.10–3.14**. See
[Platform support](https://github.com/stef-k/agent-code-guard/blob/main/docs/platform-support.md) for supported binary platforms and
source-build boundaries.

## Documentation

- [Documentation index](https://github.com/stef-k/agent-code-guard/blob/main/docs/README.md)
- [Agent workflow](https://github.com/stef-k/agent-code-guard/blob/main/docs/agent-workflow.md)
- [Usage and CLI reference](https://github.com/stef-k/agent-code-guard/blob/main/docs/usage.md)
- [Configuration](https://github.com/stef-k/agent-code-guard/blob/main/docs/configuration.md)
- [Language support](https://github.com/stef-k/agent-code-guard/blob/main/docs/language-support.md)
- [Platform support](https://github.com/stef-k/agent-code-guard/blob/main/docs/platform-support.md)
- [Skill distribution](https://github.com/stef-k/agent-code-guard/blob/main/docs/skill-distribution.md)

## Feedback, security, and license

Report defects through the [bug report form](https://github.com/stef-k/agent-code-guard/issues/new?template=bug-report.md),
propose measurements through the [candidate guard form](https://github.com/stef-k/agent-code-guard/issues/new?template=candidate-guard.md),
and follow the [security policy](https://github.com/stef-k/agent-code-guard/blob/main/SECURITY.md) for vulnerabilities.

Agent Code Guard grew from the Agent LOC Guard prototype and is now the
canonical implementation. Licensed under the [MIT License](https://github.com/stef-k/agent-code-guard/blob/main/LICENSE).
