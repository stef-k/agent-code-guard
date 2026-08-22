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

File LOC has mature default policy thresholds. Callable size and structural
nesting are active syntax guards, but neither has a universal review threshold:
projects opt in by supplying `reviewAt`. Complexity remains disabled.

## Scope rule

A new guard should be added only when all of the following hold:

- it has a deterministic measurement or objective detector;
- the concern is meaningful across languages and frameworks;
- the detector does not depend on the model inventing the measurement;
- a finding gives the agent something genuinely worth inspecting;
- the metric can be used without encouraging mechanical or readability-damaging transformations.

Project-specific architecture boundaries, framework-specific rules, arbitrary style preferences, security scanning, dependency auditing, and similar concerns are outside the universal core.

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
  "requiredPolicies": ["complexity"]
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
    -> callableSize / nesting
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

The public runner deliberately does not import or construct this pipeline while
only LOC is enabled. Tree-sitter is installed as an ordinary dependency but
remains dormant until a syntax guard requests analysis facts.

## Callable size

Enable callable physical LOC explicitly:

```json
{
  "guards": {
    "callableSize": {
      "enabled": true,
      "reviewAt": 80
    }
  }
}
```

An omitted section or `"enabled": false` disables the guard. When enabled,
`reviewAt` is required and must be a positive JSON integer; booleans, floats,
numeric strings, zero, and negative values are rejected. A callable measuring
exactly `reviewAt` passes, while `reviewAt + 1` reviews. There is no default,
FAIL threshold, override, or per-language threshold.

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
never fails. Enabling it makes syntax analysis authoritative, so malformed
applicable syntax or unavailable parser dependencies produce exit 3. When it is
disabled, LOC-only execution performs no analysis import, parser construction,
or syntax validation.

## Structural nesting

Enable executable control-flow nesting explicitly:

```json
{
  "guards": {
    "nesting": {
      "enabled": true,
      "reviewAt": 4
    }
  }
}
```

An omitted section or `"enabled": false` disables the guard. When enabled,
`reviewAt` is required and must be a positive JSON integer. Exactly the
threshold passes and a greater depth reviews. There is no default, FAIL
threshold, override, or per-language threshold.

Structural nesting is maximum active executable control-flow depth inside each
callable. It follows the normalized `ControlFlowFact` parent relationships from
the shared `AnalysisFacts`; it does not parse or reread source, inspect parser
nodes, or reconstruct language syntax. Conditions, loops, switch/match, and
try-family regions are meaningful. Indentation, braces, plain blocks, patterns,
JSX, HTML, and Vue template hierarchy are not. Else-if, case, and catch-family
normalization belongs to language adapters. Nested callables and callbacks reset
depth because they have distinct `CallableKey` values.

When callable size and nesting are both enabled, the runner calls analysis once
and passes the same facts to both guards. JSON retains PASS and REVIEW findings,
including a deterministic `details.deepestLine` when depth is nonzero. Human
output prints REVIEW findings only. Only REVIEW routes `nesting`; nesting never
fails. As with callable size, malformed applicable syntax or unavailable parser
dependencies produce exit 3 only when a syntax guard is enabled.

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

Native LOC states normalize as `ok -> PASS`, `warn -> REVIEW`, `fail -> FAIL`, and `exempt -> PASS` with the exemption reason retained. Only REVIEW and FAIL add `loc` to `requiredPolicies`. Callable size and nesting contribute only PASS or REVIEW and route their stable guard IDs only on REVIEW.

Normal exits are 0 for PASS, 1 for REVIEW, 2 for FAIL, and 3 for configuration/runtime errors. `--ci` changes REVIEW to exit 0; FAIL and errors remain 2 and 3.

## Status

File LOC is enabled by default. Callable LOC and structural nesting are
production-ready and opt-in with project-supplied review thresholds. Cyclomatic
complexity remains disabled and has no production threshold.

## License

MIT is intended, matching Agent LOC Guard.
