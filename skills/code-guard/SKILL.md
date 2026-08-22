---
name: code-guard
description: Use when creating, editing, reviewing, or refactoring source files to run deterministic cross-language code guardrails and load only the policy guidance required by triggered findings.
license: Complete terms in LICENSE.txt
---

# Code Guard

Use this skill whenever handwritten source files are created, edited, reviewed, or refactored.

Code Guard provides deterministic measurements that act as anchors for agent judgment. The measurement is objective; the response to a `REVIEW` finding still requires design judgment.

## Result states

- `PASS` — no special action is required.
- `REVIEW` — inspect the finding and either accept it with a meaningful justification or improve the code when doing so improves real clarity, cohesion, or boundaries.
- `FAIL` — do not declare normal completion until the condition is fixed or an explicitly permitted/user-approved exception applies.

## Universal rules

1. Never game a metric.
2. Preserve readability and the repository's normal formatting/style conventions.
3. Do not compress independent statements, remove useful structure/comments, obscure control flow, or minify handwritten source to lower a measurement.
4. Do not create meaningless helpers, artificial files, unnecessary abstractions, or indirection mainly to reduce a metric.
5. `REVIEW` is not an automatic refactor instruction.
6. Refactor only when the change improves the code rather than merely improving the score.
7. Do not create, broaden, or alter policy exceptions/configuration solely to make Code Guard pass without explicit user approval.
8. Do not expand the current task to unrelated pre-existing debt. Normal development checks changed/current-work files; full-repository audit is separate.

## Workflow

With Git, run the project-local Code Guard command after source edits when available:

```bash
python3 .agent-tools/code_guard.py . --changed-only --config .agent-tools/code-guard.config.json
```

Run the canonical repository runner directly when it is installed as a skill:

```bash
python3 skills/code-guard/scripts/code_guard.py . --changed-only --config examples/code-guard.config.json
```

Without Git or another VCS that can provide changed scope, pass exactly the files you created or modified. You are responsible for supplying the complete edited-file set:

```bash
python3 skills/code-guard/scripts/code_guard.py src/Foo.py src/Bar.ts tests/FooTests.cs
```

Do not create a manifest or temporary scope file. Specific positional files mean “inspect these artifacts.” A directory or `.` means a deliberate recursive audit of that scope. `--changed-only` means “ask Git for current work” and fails outside a Git repository; it never falls back to an audit.

When all guards return `PASS`, no detailed policy file needs to be loaded.

When a guard returns `REVIEW` or `FAIL`, read only the policy file named by that finding. The eventual runner must return the required policy identifiers/files in both human-readable and JSON output.

Policy references:

- file LOC: `references/loc-policy.md`
- callable size: `references/callable-size-policy.md`
- nesting depth: `references/nesting-policy.md`
- cyclomatic complexity: `references/complexity-policy.md`

Do not load unrelated guard policies merely because they exist.

## Scope

Code Guard is intentionally limited to deterministic concerns that are broadly applicable across conventional programming languages.

Guards:

- file LOC (implemented and enabled by default);
- callable LOC (reserved, disabled, and unimplemented);
- nesting depth (reserved, disabled, and unimplemented);
- cyclomatic complexity (reserved, disabled, and unimplemented).

Agent Code Guard is the canonical LOC implementation. Agent LOC Guard is the completed prototype/reference whose mature behavior was migrated from commit `75ab39d261dbc65f78815836fac90add16d265d1`.

Project-specific architecture rules, framework-specific checks, arbitrary style preferences, security scanners, and dependency auditing are outside the universal core.
