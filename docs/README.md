---
title: Agent Code Guard
permalink: /
---

# Agent Code Guard

Deterministic maintainability checks for source code and Markdown changed by a
human or coding agent. Catch oversized files and functions, deep nesting,
complex control flow, and documents that are becoming difficult to navigate.

[View on GitHub](https://github.com/stef-k/agent-code-guard) ·
[Install from PyPI](https://pypi.org/project/agent-code-guard/)

## Get started

Install the command in an isolated environment with
[pipx](https://pipx.pypa.io/):

```bash
pipx install agent-code-guard
code-guard --version
code-guard doctor
```

Then check your current changes from a Git worktree:

```bash
code-guard . --changed-only
```

No configuration is needed for ordinary use. Outside Git, pass the exact files
instead, such as `code-guard src/app.py docs/guide.md`.

- **PASS:** continue.
- **REVIEW:** inspect the finding and improve the structure when that helps.
  Keeping a cohesive file or section is a valid reviewed outcome.
- **FAIL:** correct the finding before completing the change.
- **INCOMPLETE:** restore unavailable analysis before treating the check as complete.

Code Guard measures without rewriting your files. Use it alongside tests,
compilers, linters, formatters, and design review.

## Use with a coding agent

The package includes a version-matched skill that explains how to interpret
findings. Locate it with `code-guard --skill-path`, then follow the
[skill activation guide](skill-distribution.md). The
[human and agent workflow](agent-workflow.md) covers repeated checks, compact
JSON output, and optional authorized hooks.

## Keep reviewed documents from growing unnoticed

A cohesive oversized Markdown document can use an explicitly reviewed,
source-controlled size allowance. Unchanged or smaller documents pass the
document-size guard; growth returns REVIEW, and section reviews remain active.
See the [Markdown ratchet workflow](usage.md#reviewed-markdown-document-ratchet)
for creation, updates, and limitations.

## User guides

- [Human and agent workflow](agent-workflow.md) — installation, repeated changed-work checks, REVIEW judgment, and optional authorized hooks.
- [Usage](usage.md) — installation, file selection, output, adoption ratchets, result states, and CI.
- [Configuration](configuration.md) — zero-config defaults, guard settings, exclusions, and baseline schemas.
- [Language support](language-support.md) — applicable syntax languages, extensions, and mixed-content behavior.
- [Platform support](platform-support.md) — maintained Python versions and native-wheel boundaries.
- [Skill distribution](skill-distribution.md) — version-matched agent skill discovery and export.

## Product and governance

- [Guard admission](guard-admission.md) — criteria and delivery rules for candidate guards.
- [Design decisions](design-decisions.md) — settled product and architecture decisions.

## Research and evidence

- [Analyzer feasibility](analyzer-feasibility.md)
- [Complexity evidence](complexity-evidence.md)
- [Default-threshold calibration](default-threshold-calibration.md)
- [Markdown guard evidence](markdown-guard-evidence.md)
- [Markup guard evidence](markup-guard-evidence.md)
- [Style guard evidence](style-guard-evidence.md)
