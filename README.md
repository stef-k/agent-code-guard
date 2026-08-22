# Agent Code Guard

Agent Code Guard is a portable set of deterministic guardrails for agent-assisted software development. It is now the canonical implementation of LOC Guard behavior.

It grows out of the lessons learned from [Agent LOC Guard](https://github.com/stef-k/agent-loc-guard): deterministic measurements are useful to coding agents when they act as objective anchors for review, while the agent still applies judgment instead of blindly optimizing a metric.

The project is intentionally narrow. It is not a generic clean-code prompt, IDE replacement, framework analyzer, or security scanner. A guard belongs here only when the underlying concern is broadly meaningful across conventional programming languages and can be measured deterministically.

## Core model

```text
deterministic measurement
        ↓
PASS / REVIEW / FAIL
        ↓
agent interpretation
        ↓
justify, refactor meaningfully, or resolve/escalate
```

The tool detects. The policy interprets. The agent must not game the metric.

## Initial universal guards

The first design targets four cross-language measurements:

1. **File LOC** — physical source-file size, using Agent LOC Guard as the reference implementation and policy prototype.
2. **Callable size** — physical LOC for functions/methods/callables.
3. **Nesting depth** — maximum structural nesting inside a callable.
4. **Cyclomatic complexity** — deterministic execution-path complexity.

All four guards are production defaults: file LOC reviews above 400 and fails
above 600; callable size reviews above 80 physical LOC; structural nesting
reviews above depth 4; and cyclomatic complexity reviews above 15. The three
syntax guards are REVIEW-only. Only file LOC can FAIL.

## Adding new guards

Agent Code Guard should remain deliberately small. A new candidate guard is not accepted merely because a metric can be computed; its evaluation issue must gather evidence that the concern belongs in the universal deterministic core.

The primary admission gate asks whether the candidate:

1. has a **deterministic anchor** — identical source/configuration produces the same measurement or detection without model judgment or unstable external state;
2. has **real engineering value** — the condition corresponds to a maintainability, readability, cohesion, control-flow, or design concern genuinely worth inspecting;
3. has **broad applicability** — the underlying concern is useful across a meaningful range of conventional languages/stacks, even if parsing requires language-specific adapters;
4. has a **distinct responsibility** — it does not merely duplicate a mature formatter, compiler, linter, scanner, test runner, dependency tool, or framework analyzer;
5. has **stable measurement semantics** — what is measured can be defined precisely without hiding important language differences;
6. produces **actionable, explainable findings** — the relevant source identity/range and trigger can be understood without raw parser internals;
7. has a **useful state model** — PASS / REVIEW / FAIL semantics can be justified, with FAIL requiring substantially stronger evidence than REVIEW;
8. has an **acceptable signal-to-noise ratio** on representative code, not only synthetic fixtures.

Candidates that pass that gate must also demonstrate threshold/configuration evidence, resistance to metric gaming, compatibility with runner-owned scope, reasonable architecture/dependency cost, deterministic failure behavior, and portable deterministic tests.

For numerical candidates, keep three questions separate: **can we measure it deterministically?**, **is the measurement useful?**, and **can we justify a universal default threshold?** Passing the first two does not require inventing a default; an opt-in configurable guard is a valid outcome.

Every new proposal should begin as a **Candidate guard** issue using the repository issue template and end with one of four explicit decisions: **ACCEPT**, **ACCEPT — CONFIGURABLE ONLY**, **NEEDS MORE EVIDENCE**, or **REJECT / OUT OF SCOPE**. Accepted guards should normally ship as one vertical production slice from deterministic provider/facts through configuration, runner/result/policy integration, tests, CI, and documentation.

See [Guard Admission and Candidate Evaluation](docs/guard-admission.md) for the full evidence checklist, decision record, and delivery rules.

Project-specific architecture boundaries, framework-specific rules, arbitrary style preferences, security scanning, dependency auditing, and similar concerns remain outside the universal core unless a candidate evaluation produces evidence for a distinct Code Guard responsibility.

## Agent-facing architecture

The experience is one skill and one public command, backed by modular internal guards:

```text
one skill
one entry point
one result model
multiple independent guards
```

Detailed guard policies are kept separate so agents load only the policy needed by a triggered finding.

```text
skills/code-guard/
├── SKILL.md
└── references/
    ├── loc-policy.md
    ├── callable-size-policy.md
    ├── nesting-policy.md
    └── complexity-policy.md
```

Expected workflow:

```text
read compact SKILL.md
        ↓
run Code Guard on current changes
        ↓
receive PASS / REVIEW / FAIL findings
        ↓
load only policy files named by triggered findings
        ↓
apply judgment without gaming metrics
```

The machine-readable result exposes required policy identifiers only for actionable guards, for example:

```json
{
  "overall": "review",
  "requiredPolicies": ["nesting"]
}
```

## Universal behavioral rules

These apply to every guard:

- Never game a metric.
- Preserve readability and normal project formatting.
- `REVIEW` requires inspection, not automatic refactoring.
- Refactor only when the result improves real boundaries or clarity.
- Do not create artificial helpers, files, abstractions, or indirection mainly to lower a metric.
- `FAIL` blocks normal completion unless the condition is fixed or an explicitly permitted exception applies.
- Agents must not create or broaden policy exceptions without explicit user approval.
- Normal development checks current changed files; unrelated legacy debt belongs to explicit audit work.

## Scope modes

Install Agent Code Guard and all of its runtime dependencies once from a checkout:

```bash
python -m pip install .
```

For editable development, `python -m pip install -e .` provides the same
dependency set and command. The normal installed command is `code-guard`.

Code Guard keeps three scope sources distinct:

- Git-derived current work: `--changed-only`, `--staged`, or `--base-ref <ref>` asks Git for scope and requires a Git repository.
- Explicit caller scope: one or more positional file paths inspect exactly those existing artifacts, subject to each guard's applicability and exclusions.
- Explicit audit scope: a positional directory or `.` recursively inspects that supplied tree. It does not mean changed-only.

With Git, normal agent use evaluates the complete current change set relative to `HEAD`:

```bash
code-guard . --changed-only
```

Without Git or another VCS, the coding agent must pass exactly the files it created or modified:

```bash
code-guard src/Foo.py src/Bar.ts tests/FooTests.cs
```

No manifest or intermediate file list is needed. A missing explicit path is a scope error (exit 3), while unsupported existing artifacts remain valid scope and are simply ignored by guards that do not apply. Git-derived deleted files remain ignored under ACMR selection.

Full-directory analysis remains a separate deliberate audit mode:

```bash
code-guard .
```

Pull-request CI should evaluate files added or modified by the PR relative to its base rather than unrelated pre-existing oversized files.

## Production syntax infrastructure

The shipped internal pipeline accepts only the files already selected by the runner:

```text
resolve_scope() -> ResolvedScope.files
    -> source/container regions
    -> cached Tree-sitter parser
    -> immutable provider-neutral facts (built once)
    -> callableSize / nesting / complexity
```

Ordinary files are identity-mapped regions. Vue template/style content is ignored;
each inline `script` region is mapped back to exact original `.vue` byte coordinates.
The production adapters support Python, Go, Kotlin, C#, Java, JavaScript,
TypeScript, JSX, TSX, Vue JavaScript/TypeScript scripts, C++, Rust, PHP, Swift,
and Dart. C++ dispatch includes `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, and `.hxx`;
ambiguous generic `.h` files remain syntax-inapplicable until language context is
available. Unsupported ordinary artifacts
are not syntax errors. Supported malformed syntax, unsupported explicit Vue
script languages, external Vue scripts, or a missing required grammar fail
deterministically instead of returning partial facts.

The standard Python 3.10+ installation includes the syntax infrastructure.
`pyproject.toml` is the single canonical declaration for the exact production
pins `tree-sitter==0.26.0` and `tree-sitter-language-pack==1.14.3`. Both include native components. Published
wheels cover CPython 3.10+ on mainstream Windows, macOS, and Linux platforms;
unsupported platforms may require a local native build and are not silently
downgraded to regex analysis. The language pack wheel is about 2–2.4 MB before
installation. Parser instances are cached by embedded language inside one
provider, and each executable region is parsed/extracted once for reuse by all
enabled syntax guards.

PHP files use one identity-mapped whole-file executable region. The pinned PHP
grammar exposes PHP declarations alongside inert HTML `text` nodes, so mixed
files retain exact original bytes and paths without copying or splitting PHP
that can legally span close/reopen tags. HTML does not emit executable facts.

Zero-config execution uses this syntax pipeline because all three syntax guards
are active by default. Supported malformed syntax or an unavailable
required provider therefore produces deterministic exit 3. When both syntax
guards and complexity are explicitly disabled, the public runner does not import
or construct the pipeline: Tree-sitter remains dormant and execution is LOC-only.

## Callable size

Callable physical LOC is enabled by default at REVIEW greater than 80. A project
may concisely override the threshold:

```json
{
  "guards": {
    "callableSize": {
      "reviewAt": 100
    }
  }
}
```

The example value demonstrates override syntax; it is not a recommendation.

An omitted section, an empty object, or `"enabled": true` uses the built-in 80.
A threshold-only object enables the guard with that override. Explicit
`"enabled": false` disables it and is authoritative even if `reviewAt` is also
present. While enabled, an explicit `reviewAt` must be a positive JSON integer;
booleans, floats, numeric strings, null, zero, and negative values are rejected.
Exactly `reviewAt` passes and `reviewAt + 1` reviews. There is no FAIL or
per-language threshold.

The runner resolves scope once, runs LOC directly, then builds one shared
`AnalysisFacts` value only if an enabled syntax guard requires it. Callable size
uses each `CallableFact.source_range.physical_loc`; it does not reread source,
reconstruct ranges, or contain Tree-sitter/language-specific logic. JSON retains
PASS and REVIEW findings; human output prints REVIEW findings only:

```json
{
  "path": "src/Foo.ts",
  "callable": "Foo.process",
  "range": {"startLine": 20, "endLine": 108},
  "measured": 89,
  "state": "review",
  "thresholds": {"reviewAt": 80},
  "embeddedLanguage": "typescript"
}
```

Only a REVIEW result adds `callableSize` to `requiredPolicies`. Callable size
never fails. Because it is enabled by default, syntax analysis is normally
authoritative. LOC-only execution requires callable size, nesting, and
cyclomatic complexity to be explicitly disabled.

## Structural nesting

Structural nesting is enabled by default at REVIEW greater than depth 4. It may
be disabled explicitly:

```json
{
  "guards": {
    "nesting": {
      "enabled": false
    }
  }
}
```

An omitted section, an empty object, or `"enabled": true` uses the built-in 4.
A threshold-only object enables the guard with that override. Explicit
`"enabled": false` wins even when `reviewAt` is present. While enabled, an
explicit threshold must be a positive JSON integer. Exactly the threshold passes
and a greater depth reviews. There is no FAIL or per-language threshold.

Structural nesting is maximum active executable control-flow depth inside each
callable. It follows the normalized `ControlFlowFact` parent relationships from
the shared `AnalysisFacts`; it does not parse or reread source, inspect parser
nodes, or reconstruct language syntax. Conditions, loops, switch/match, and
try-family regions are meaningful. Indentation, braces, plain blocks, patterns,
JSX, HTML, and Vue template hierarchy are not. Else-if, case, and catch-family
normalization belongs to language adapters. Nested callables and callbacks reset
depth because they have distinct `CallableKey` values.

When multiple syntax guards are enabled, the runner calls analysis once and
passes the same facts to each guard. JSON retains PASS and REVIEW findings,
including a deterministic `details.deepestLine` when depth is nonzero. Human
output prints REVIEW findings only. Only REVIEW routes `nesting`; nesting never
fails. As with callable size, malformed applicable syntax or unavailable parser
dependencies produce exit 3 only when a syntax guard is enabled.

## Cyclomatic complexity

Cyclomatic complexity is enabled by default at REVIEW greater than 15. Its
configuration key is `guards.cyclomaticComplexity`; a REVIEW routes the stable
result and policy ID `complexity`. Omission, an empty object, or `enabled: true`
uses 15. A positive JSON integer `reviewAt` is an authorized project override.
`enabled: false` disables the guard and wins even if an invalid `reviewAt` is
also present. Exactly the effective threshold passes; greater values review;
complexity never fails.

The language-neutral guard computes `1 +` the number of normalized
`DecisionFact` values owned by each `CallableKey`. Categories include normalized
conditions, loops, catches, ternaries, executable switch/when/match arms,
pattern guards, and Python comprehension/generator decisions when present.
Short-circuit booleans and fallback/null-aware constructs contribute zero.
Nested and anonymous callables, including mainstream lambdas, own their decisions
independently and restart from baseline 1. JSON details contain the callable's
`boundaryKind` and sorted non-zero decision-category counts; human output prints
only REVIEW findings.

## Canonical LOC implementation

Agent Code Guard owns LOC behavior. The unified runner supports explicit files/directories, full audit, and the `--changed-only`, `--staged`, `--base-ref <ref>`, `--json`, and `--ci` modes:

```bash
code-guard . --changed-only
```

Agent LOC Guard is the completed prototype/reference whose mature behavior at commit `75ab39d261dbc65f78815836fac90add16d265d1` was migrated here, including:

- warning versus hard-failure semantics;
- changed-file scope;
- exclusions and generated files;
- explicit exceptions;
- CI behavior;
- anti-gaming policy;
- agent reasoning around cohesion and meaningful refactoring.

There is no runtime dependency, synchronization layer, or second LOC implementation. Retirement of the prototype repository remains issue #3.

## Result and exit contract

Native LOC states normalize as `ok -> PASS`, `warn -> REVIEW`, `fail -> FAIL`, and `exempt -> PASS` with the exemption reason retained. Only REVIEW and FAIL add `loc` to `requiredPolicies`. Callable size, nesting, and complexity contribute only PASS or REVIEW and route their stable guard IDs only on REVIEW.

Normal exits are 0 for PASS, 1 for REVIEW, 2 for FAIL, and 3 for configuration/runtime errors. `--ci` changes REVIEW to exit 0; FAIL and errors remain 2 and 3.

## Status

File LOC at 400/600, callable LOC at 80, structural nesting at 4, and cyclomatic
complexity at 15 are enabled by default. Syntax guards are REVIEW-only and
support authorized project overrides or explicit disablement. One shared syntax
analysis pass serves every enabled syntax guard.

## License

MIT is intended, matching Agent LOC Guard.
