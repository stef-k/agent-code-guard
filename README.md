# Agent Code Guard

<p align="center">
  <img src="https://raw.githubusercontent.com/stef-k/agent-code-guard/main/assets/agent-code-guard-mark.svg" width="180" alt="Agent Code Guard project mark">
</p>

Deterministic guardrails for agent-assisted software development.

[![Production Analysis](https://github.com/stef-k/agent-code-guard/actions/workflows/analysis.yml/badge.svg)](https://github.com/stef-k/agent-code-guard/actions/workflows/analysis.yml)
[![PyPI](https://img.shields.io/pypi/v/agent-code-guard?logo=pypi&logoColor=white)](https://pypi.org/project/agent-code-guard/)
[![Python 3.10–3.14](https://img.shields.io/badge/Python-3.10%E2%80%933.14-3776AB?logo=python&logoColor=white)](https://github.com/stef-k/agent-code-guard/blob/main/docs/platform-support.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/stef-k/agent-code-guard/blob/main/LICENSE)

Code Guard gives coding agents objective measurements and **PASS / REVIEW /
FAIL** signals while leaving design decisions to agent and user judgment.

```text
deterministic measurement
        ↓
PASS / REVIEW / FAIL
        ↓
agent judgment
```

## Installation

[pipx](https://pipx.pypa.io/) keeps the command isolated from project
environments:

```bash
pipx install agent-code-guard
```

See the [usage guide](https://github.com/stef-k/agent-code-guard/blob/main/docs/usage.md)
for a virtual-environment alternative and developer installation.

## Quick start

Run all enabled, applicable guards over your current Git work:

```bash
code-guard . --changed-only
```

Git determines the edited-file candidates, Code Guard applies every enabled
and applicable guard, and project or user exclusions remain authoritative. No
configuration file is required.

## Result model

- **PASS** — no special action.
- **REVIEW** — inspect the finding and decide whether meaningful improvement is
  warranted. REVIEW is not automatic refactoring.
- **FAIL** — blocks normal completion until fixed or an explicitly authorized
  exception applies.

**Never game the metric.** Preserve clarity and useful structure; do not create
artificial helpers, files, abstractions, formatting, or exclusions merely to
lower a measurement.

## Default guards

| Guard | Default |
| --- | --- |
| File LOC | REVIEW >400, FAIL >600 |
| Callable size | REVIEW >80 physical LOC |
| Structural nesting | REVIEW >4 |
| Cyclomatic complexity | REVIEW >15 |
| Markdown document size | REVIEW >800 physical lines |
| Markdown direct-section size | REVIEW >200 physical lines |

Comparisons are strictly greater-than, so equality passes. All guards except
file LOC are REVIEW-only; only file LOC can FAIL.

Agent Code Guard intentionally remains small. A new guard must provide distinct,
deterministic agent-guardrail value rather than merely duplicate mature
conventional tooling. See [Guard admission](https://github.com/stef-k/agent-code-guard/blob/main/docs/guard-admission.md).

## Common workflows

Normal Git work:

```bash
code-guard . --changed-only
```

Explicit agent-owned scope without Git:

```bash
code-guard src/Foo.py src/Bar.ts docs/guide.md
```

Pull request or branch comparison:

```bash
code-guard . --base-ref origin/main --ci
```

The actual base ref must exist or be fetched correctly in the chosen CI
environment.

Deliberate full audit:

```bash
code-guard .
```

Changed work is not a full audit. Use Git selection during normal development;
do not repeatedly scan unrelated repository history after every edit.

## Supported languages and formats

Syntax guards support Python, Go, Kotlin, C#, Java, JavaScript, TypeScript, JSX,
TSX, Vue JavaScript/TypeScript script regions, C++, Rust, PHP, Swift, and Dart.
Markdown guards apply to `.md` files.

Important boundaries:

- Generic `.h` files are not syntax-dispatched because their language context
  is ambiguous.
- `.markdown` is not currently enabled for Markdown guards.
- Vue template and style regions are not executable syntax input.
- Unsupported artifacts are simply inapplicable.
- Malformed applicable syntax or a required provider failure is a fail-closed
  tool error, never heuristic partial analysis.

See [Language support](https://github.com/stef-k/agent-code-guard/blob/main/docs/language-support.md)
for extension and mixed-content details.

## Agent integration

CLI-only use requires no skill export. Each installed distribution also carries
a version-matched Code Guard skill payload for agent workflows:

```bash
code-guard --skill-path
code-guard --export-skill <target-directory>
```

See [Skill distribution](https://github.com/stef-k/agent-code-guard/blob/main/docs/skill-distribution.md)
for discovery, export, and integration guarantees. The checkout compatibility
runner is for repository and skill compatibility, not primary end-user
installation.

## Configuration

Built-in defaults require no config. A minimal project configuration is:

```json
{
  "version": 1
}
```

Use configuration only when a project has a concrete policy reason to change a
guard or scope. See the [Configuration guide](https://github.com/stef-k/agent-code-guard/blob/main/docs/configuration.md).

## Documentation

- [Documentation index](https://github.com/stef-k/agent-code-guard/blob/main/docs/README.md)
- [Usage](https://github.com/stef-k/agent-code-guard/blob/main/docs/usage.md)
- [Configuration](https://github.com/stef-k/agent-code-guard/blob/main/docs/configuration.md)
- [Language support](https://github.com/stef-k/agent-code-guard/blob/main/docs/language-support.md)
- [Platform support](https://github.com/stef-k/agent-code-guard/blob/main/docs/platform-support.md)
- [Skill distribution](https://github.com/stef-k/agent-code-guard/blob/main/docs/skill-distribution.md)

## Platform support

The maintained interpreter range is **CPython 3.10–3.14**. The normal binary
installation envelope is:

- Windows x86-64 and ARM64;
- macOS x86-64 and ARM64;
- Linux glibc 2.34 or newer on x86-64 and ARM64.

Source builds outside that binary envelope are best effort and are not
release-supported. See [Platform support](https://github.com/stef-k/agent-code-guard/blob/main/docs/platform-support.md)
for exact wheel and deployment boundaries.

## Feedback and security

Report normal defects through the [bug report form](https://github.com/stef-k/agent-code-guard/issues/new?template=bug-report.md)
and propose new measurements through the [Candidate guard form](https://github.com/stef-k/agent-code-guard/issues/new?template=candidate-guard.md).
For vulnerability reporting, follow the repository [Security policy](https://github.com/stef-k/agent-code-guard/blob/main/SECURITY.md).

## Background and license

Agent Code Guard grew from the Agent LOC Guard prototype and is now the
canonical implementation. It remains focused on deterministic measurements
that complement—not replace—tests, compilers, formatters, linters, security
tools, or design judgment.

Licensed under the [MIT License](https://github.com/stef-k/agent-code-guard/blob/main/LICENSE).
