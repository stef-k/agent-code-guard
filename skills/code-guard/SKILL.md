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

With Git, run the installed Code Guard command after source edits:

```bash
code-guard . --changed-only --config .agent-tools/code-guard.config.json
```

The normal packaged workflow installs Code Guard and its syntax dependencies in
one step, then uses the installed command:

```bash
python -m pip install .
code-guard . --changed-only --config examples/code-guard.config.json
```

The compatibility runner remains available directly from a repository checkout:

```bash
python3 skills/code-guard/scripts/code_guard.py . --changed-only --config examples/code-guard.config.json
```

`pyproject.toml` canonically owns the production pins. Tree-sitter remains
dormant during LOC-only execution; failure to load a required provider or
grammar is a deterministic tool error during normal zero-config syntax analysis.
Disabling every syntax guard preserves the lazy no-Tree-sitter path. A strictly
LOC-only result also requires both Markdown guards to be explicitly disabled.

Without Git or another VCS that can provide changed scope, pass exactly the files you created or modified. You are responsible for supplying the complete edited-file set:

```bash
code-guard src/Foo.py src/Bar.ts tests/FooTests.cs
```

Do not create a manifest or temporary scope file. Specific positional files mean “inspect these artifacts.” A directory or `.` means a deliberate recursive audit of that scope. `--changed-only` means “ask Git for current work” and fails outside a Git repository; it never falls back to an audit.

Prefer normal zero-config scope and respect project `scope.exclude`; do not
remove or alter exclusions merely to silence findings. Repeated
`--scope-exclude` is caller-supplied all-guard scope policy and composes with
project exclusions. LOC `--exclude` remains LOC-specific. Explicit files may
intentionally inspect Git-ignored or built-in-pruned artifacts, unless Code
Guard `scope.exclude` or `--scope-exclude` removes them.

When all guards return `PASS`, no detailed policy file needs to be loaded.

When a guard returns `REVIEW` or `FAIL`, read only the policy file named by that finding. The runner returns required policy identifiers/files in both human-readable and JSON output.

Policy references:

- file LOC: `references/loc-policy.md`
- callable size: `references/callable-size-policy.md`
- nesting depth: `references/nesting-policy.md`
- cyclomatic complexity: `references/complexity-policy.md`
- Markdown document/section size: `references/markdown-size-policy.md`

Do not load unrelated guard policies merely because they exist.

## Scope

Code Guard is intentionally limited to deterministic concerns that are broadly applicable across conventional programming languages.

Guards:

- file LOC (implemented and enabled by default);
- source/container and syntax facts (production infrastructure, not a guard);
- callable LOC (implemented and enabled by default; REVIEW greater than 80);
- structural nesting (implemented and enabled by default; REVIEW greater than 4);
- cyclomatic complexity (implemented and enabled by default; REVIEW greater than 15).
- Markdown document physical size (implemented for `.md` and enabled by default; REVIEW greater than 800);
- Markdown direct-section physical size (implemented for `.md` and enabled by default; REVIEW greater than 200).

Callable LOC needs no invented configuration to activate it. Omission or
`enabled: true` uses 80; an authorized positive-integer `reviewAt` overrides it,
and `enabled: false` disables it. Exactly the effective threshold passes;
larger callables review and never fail. Load
`references/callable-size-policy.md` only when `callableSize` appears in
`requiredPolicies`.

Structural nesting is executable control-flow depth, not visual, markup, brace,
or indentation depth. Omission or `enabled: true` uses 4; an authorized
positive-integer `reviewAt` overrides it, and `enabled: false` disables it.
Exactly the effective depth passes; greater depth reviews and never fails. Load `references/nesting-policy.md` only when `nesting`
appears in `requiredPolicies`.

Cyclomatic complexity is baseline 1 plus normalized decisions owned by the
callable. Omission or `enabled: true` uses 15; an authorized positive-integer
`reviewAt` overrides it, and `enabled: false` disables it. Short-circuit
booleans and fallback/null-aware constructs contribute zero. Lambda boundaries
are independent. Exactly the effective threshold passes; greater complexity
reviews and never fails. Load `references/complexity-policy.md` only when
`complexity` appears in `requiredPolicies`.

Markdown document and direct-section size count all physical lines. Sections
run from a supported heading through the line before the next heading of any
level, or EOF. Exact effective thresholds pass; greater measurements review and
never fail. Load `references/markdown-size-policy.md` when either
`markdownDocumentSize` or `markdownSectionSize` appears in `requiredPolicies`.
Review navigation and responsibility without mechanically splitting coherent
specifications or gaming headings/formatting.

Do not invent configuration, disable a guard, or raise its threshold
merely to silence a finding. Respect built-ins and only project/user-authorized overrides.
REVIEW requires inspection and justification, not mandatory refactoring.

Agent Code Guard is the canonical LOC implementation. Agent LOC Guard is the completed prototype/reference whose mature behavior was migrated from commit `75ab39d261dbc65f78815836fac90add16d265d1`.

Project-specific architecture rules, framework-specific checks, arbitrary style preferences, security scanners, and dependency auditing are outside the universal core.
