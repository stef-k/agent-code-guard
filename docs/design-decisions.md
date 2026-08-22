# Design Decisions

This document records the conclusions reached while generalizing Agent LOC Guard into Agent Code Guard. It is intentionally decision-focused so future implementation work can distinguish settled product boundaries from open technical questions.

## D1 — One agent-facing skill

Agent Code Guard is one skill rather than separate LOC, complexity, nesting, and callable-size skills.

Rationale:

- agents should have one predictable quality-guard entry point;
- universal behavioral rules should not be duplicated across skills;
- the deterministic providers can still remain independently implemented and tested;
- a single normalized result model reduces agent and CI integration complexity.

## D2 — Detailed policies are loaded lazily

`SKILL.md` stays compact. Each guard has its own policy reference.

The runner must identify the policy references required by triggered findings so an agent does not load LOC guidance when only complexity fired, or vice versa.

This is both a context-efficiency decision and a separation-of-concerns decision.

## D3 — Deterministic anchor required

A guard is eligible for the universal core only when it has an objective deterministic measurement/detector.

Agent judgment begins after detection. The model must not be asked to invent the score that triggers its own review.

A metric being measurable is not sufficient by itself; the finding must also correspond to a broadly useful engineering concern.

## D4 — Universal across languages and stacks

The core policy must make sense for Go, Python, Kotlin, C#, Java, JavaScript/TypeScript, and similar conventional languages.

Language-aware parsing/adapters are allowed internally. Language-specific behavioral policy is not part of the universal core unless required solely to interpret syntax.

## D5 — Initial guard set is intentionally small

Initial candidates:

1. file LOC;
2. callable LOC;
3. nesting depth;
4. cyclomatic complexity.

File LOC is the mature prototype. The other three require cross-language feasibility and threshold validation.

Duplication may be reconsidered later, but its expected noise makes it unsuitable for the first implementation.

## D6 — PASS / REVIEW / FAIL is the common agent model

- `PASS`: no intervention.
- `REVIEW`: inspect and apply judgment; do not automatically refactor.
- `FAIL`: blocks normal completion unless fixed or explicitly excepted.

Not every guard must expose every state. In particular, callable size, nesting, and cyclomatic complexity should begin as `PASS / REVIEW` unless evidence supports a reliable hard threshold.

## D7 — Warnings are review triggers, not scores to optimize

The purpose of a metric is to force attention to a potentially important condition.

Agents must not mechanically transform code until the number falls below a threshold. A warning can be accepted when the design is genuinely clearer in its current form.

## D8 — No metric gaming

Metric reduction is invalid when achieved by degrading readability or maintainability.

Examples of prohibited behavior include:

- combining independent statements/declarations onto fewer lines to reduce LOC;
- minifying or quasi-minifying handwritten source;
- removing useful comments or structure merely to reduce counts;
- extracting meaningless helpers merely to reduce callable size or complexity;
- hiding decisions behind opaque boolean expressions or wrappers;
- replacing clear structured control flow with clever constructs mainly to lower nesting/complexity;
- fragmenting cohesive files into artificial pieces merely to satisfy file LOC.

Project formatting conventions take precedence over metric optimization.

## D9 — Agents cannot self-authorize exceptions

Agents may honor existing explicit exceptions. They must not create, broaden, or alter exceptions/configuration solely to make Code Guard pass without explicit user approval.

Exception records should carry meaningful reasons.

## D10 — Changed-code-first normal workflow

Normal development evaluates the complete current change set relative to `HEAD`:

- staged changes;
- unstaged changes;
- untracked, non-ignored source files.

Full-repository checking is a separate audit operation.

For pull requests, CI should evaluate files added/modified relative to the PR base so unrelated legacy debt does not block adoption.

## D11 — Do not duplicate mature project tooling unnecessarily

Build, test, lint, formatting, security, dependency, and framework-specific tooling already have strong ecosystems and project-specific semantics.

Agent Code Guard may integrate with such tools later, but they are not part of the universal deterministic guard set merely to make the project resemble an IDE.

## D12 — Agent Code Guard owns canonical LOC behavior

Agent LOC Guard established important behavior around:

- deterministic file measurement;
- soft review thresholds versus hard limits;
- exclusions;
- changed-file scope;
- explicit exceptions;
- anti-gaming policy;
- warning interpretation.

The mature implementation from Agent LOC Guard commit `75ab39d261dbc65f78815836fac90add16d265d1` was migrated into the internal LOC guard. Agent LOC Guard is the completed prototype/reference, not a runtime dependency or parallel implementation. Its retirement is tracked separately in issue #3.

The public runner owns aggregation and output. LOC owns its configuration, measurement, matching, thresholds, exemptions, and native statuses. Repository discovery and file selection are separate because the runner establishes repository context and LOC consumes selected candidates today; further sharing waits for evidence from issue #4.

## D15 — Normalized LOC result preserves native context

LOC maps `ok` to `PASS`, `warn` to `REVIEW`, `fail` to `FAIL`, and `exempt` to `PASS`. Each finding retains counted LOC, effective thresholds, override index, native status, and exemption reason. Only REVIEW or FAIL routes the `loc` policy.

Configuration is one Code Guard document with mature LOC fields under `guards.loc`. Disabled future guard entries are declarative placeholders only; no generic rule engine or analyzer behavior is implied.

## D16 — Scope validity is runner-owned

File-selection arguments are part of the public Code Guard contract. The runner validates mutually exclusive modes, non-empty base refs, and base-ref resolvability before invoking any guard, so disabling LOC cannot turn an invalid invocation into `PASS`.

## D17 — Global LOC thresholds use strict JSON integers

Code Guard intentionally tightens global LOC threshold configuration to require positive JSON integers rather than preserving Agent LOC Guard's historical coercion. Numeric strings, booleans, and floats are rejected; threshold overrides retain their existing strict integer semantics. This compatibility tightening keeps the unified configuration explicit and deterministic.

## D13 — New thresholds require evidence

No universal thresholds for callable size, nesting, or cyclomatic complexity are considered settled.

They must be evaluated against representative source fixtures and real code across multiple languages before becoming defaults. If cross-language comparability is weak, thresholds may remain configurable rather than pretending one universal number is correct.

## D14 — Parser/provider technology is an open implementation decision

Tree-sitter and language-specific analyzers/adapters are possible approaches. No parser stack is selected yet.

The first technical milestone must prototype at least Python, Go, Kotlin, and C# and compare:

- parsing accuracy;
- callable discovery;
- control-flow/nesting measurement;
- complexity consistency;
- install/runtime portability;
- dependency weight;
- ease of packaging as an agent skill.

Technology should be selected from that evidence.

## D18 — Callable analysis uses a provider-neutral language adapter

Phase A provisionally selected a provider-neutral language adapter after proving
Python, Go, Kotlin, and C#. Phase B added Java, JS, TS, JSX, TSX, and Vue and
confirmed the provider choice while changing the top-level boundary.

Production should use:

```text
source/container adapter
    -> executable regions with original location mapping
    -> provider-neutral language adapter
    -> normalized callable/control facts
    -> independent metrics
```

Tree-sitter remains the recommended initial pinned provider. Vue proves one file
cannot be assumed to equal one parser language. Raw parser nodes must not become
guard APIs, and native backends remain possible where later evidence justifies
them. Template/style metrics are separate guard families tracked in issue #6.

The research dependency is not yet a shipped Code Guard dependency. Packaging
and cross-platform wheel verification are a separate production slice.

## D19 — Callable measurement semantics are range- and scope-based

Callable physical LOC is the inclusive physical source range from attached
decorator/annotation/attribute through the final callable token. It includes
signature, blank, comment, brace, and nested-declaration lines. This is distinct
from canonical file LOC.

Nesting is maximum active meaningful control-flow depth, not indentation or
brace depth. Cyclomatic complexity is one plus documented syntactic decisions.
Named local callables reset control metrics. Phase B qualifies the range start to
include stable JS/TS lexical assignment ownership and maps Vue ranges to the
original container. Named JS-family arrows/function expressions are callables;
truly anonymous JS-family callbacks use deterministic source-coordinate
identities and independent scopes. Phase A and Java lambdas remain opaque, so
lambda policy is explicitly language-specific. See `analyzer-feasibility.md` for
the exact construct mapping and limitations.

## D20 — No new universal thresholds are established

This Phase A conclusion survived Phase B. The expanded fixture corpus supports
configurable callable LOC and nesting review points but does not justify
universal defaults. Complexity requires language-specific interpretation for
comprehensions, fallback operators, switch forms, JSX expressions, and callback
boundaries. No production REVIEW or FAIL threshold is enabled by the prototype.

## D21 — Scope resolution precedes guard applicability

The runner resolves one normalized file scope before invoking guards. Git-derived modes require an enclosing Git repository. Positional files and directories work independently of Git; missing explicit paths are errors, while existing artifacts remain in common scope even when LOC does not support their extension. Each guard receives the same common scope and applies its own inclusion and exclusion rules. A directory or `.` is always a deliberate recursive audit, never a fallback for a failed Git mode.

## D22 — Syntax analysis is a lazy, shared production service

The production syntax pipeline accepts `ResolvedScope.files`; it does not walk,
query Git, apply `.gitignore`, or own exclusions. Applicability is limited to
mapping each supplied file to a supported source/container adapter. This keeps
future scope policy in issue #16 and preserves one runner-owned selection.

LOC consumes selected files directly. Syntax facts are built only when an
enabled syntax guard needs them, so the current LOC-only runner has no parser
startup, installation, or syntax-validity dependency.

One analysis call creates byte-mapped executable regions, parses each region
once with provider-owned parsers cached by embedded language, and extracts one
immutable `AnalysisFacts` value. Future callable LOC, nesting, and complexity
guards share that value. Facts contain callable ownership/ranges, structural
control relationships, and categorized decisions rather than public findings or
precomputed metric totals. A range-qualified immutable callable key disambiguates
duplicate lexical display identities across regions and anchors parent, control,
and decision relationships. Tree-sitter nodes never cross the extraction boundary.

Tree-sitter 0.26.0 and tree-sitter-language-pack 1.14.3 are the pinned initial
provider. Python 3.10+ and a compatible platform wheel/native build are required
only when syntax analysis is invoked. Unsupported ordinary artifacts are
inapplicable; a supported artifact with malformed syntax or an unavailable
provider/grammar is a deterministic analysis error suitable for the existing
runner exit-3 boundary.

## D23 — Second-wave languages preserve the production fact contract

C++, Rust, PHP, Swift, and Dart extend the shipped adapter tables and lexical
identity/range helpers without changing `AnalysisFacts`. Their functions,
methods, constructors/initializers, and mainstream closures emit the existing
callable, control, and decision facts. Assigned closures use their stable lexical
owner; anonymous closures use original source-coordinate identities and reset
control measurement at their boundary.

PHP validates a second container shape: the whole mixed file is one
identity-mapped PHP region because the grammar keeps HTML inert while allowing
PHP syntax to span tags. C++ preprocessing remains lexical: directives are
parsed but not expanded or configured, and runtime decisions never arise from
`#if` itself. Generic `.h` remains excluded because suffix alone cannot choose C
versus C++ honestly.

Rust `if let`/`while let` use ordinary condition/loop facts; patterns add no
decision, non-wildcard match arms do, and explicit match guards add a separate
`pattern_guard`. Swift `guard` is a condition whose failure body is structurally
nested while following statements are not; non-default switch arms and `where`
guards are decisions. PHP `??`, Swift optional navigation/coalescing, and Dart
null-aware/coalescing remain non-decisions, consistent with the settled fallback
policy. These qualifications strengthen callable LOC and nesting Outcome B and
strengthen while further qualifying complexity Outcome C. No syntax guard or
threshold is enabled.

## D24 — One standard installation with lazy syntax activation

Agent Code Guard has one Python 3.10+ installation and one capability set.
`pyproject.toml` canonically owns the runtime dependency pins, including
Tree-sitter and the language pack, and `python -m pip install .` installs the
complete product. There are no analysis/full/minimal editions or runtime grammar
downloads.

Unified installation does not imply eager activation. LOC-only execution does
not import the analysis package, load Tree-sitter, construct parsers, or parse
source. Syntax dependencies remain dormant until a syntax guard requests
`AnalysisFacts`.

## D25 — Callable physical LOC is an opt-in shared-facts guard

Callable size is the first active syntax guard. It consumes only
`CallableFact.source_range.physical_loc` from the immutable facts created once
by runner orchestration. It performs no source discovery, reads, parsing, range
reconstruction, or language-specific measurement.

The `guards.callableSize` section is disabled when omitted or explicitly false.
Enabling it requires a positive JSON integer `reviewAt`; there is no universal
default, FAIL threshold, override, or per-language threshold. Exactly the
threshold passes and larger callables review. JSON includes every measured
callable while human text includes only REVIEW findings. Only REVIEW routes the
`callableSize` policy.

The runner's explicit `needs_analysis` decision is the extension seam for the
next syntax guard: scope is resolved once, LOC runs directly, one analysis value
is built if any syntax guard needs it, and all such guards consume that value.
Disabled syntax guards retain LOC-only behavior without analysis imports,
provider initialization, parser construction, or syntax validation.

## D26 — Structural nesting is normalized executable control depth

The opt-in `nesting` guard consumes only `CallableFact` and `ControlFlowFact`
relationships from the runner's single shared `AnalysisFacts` value. It groups
facts by range-qualified `CallableKey`, follows `parent_control_range`, and adds
one only when `increases_nesting` is true. The maximum active depth is therefore
computed without source reads, parser nodes, syntax reconstruction, or language
concepts inside the guard.

Executable conditions, loops, switch/match, and try-family controls are
meaningful. Visual indentation, braces, plain blocks, pattern depth, JSX, HTML,
and Vue template hierarchy are not. Language adapters remain authoritative for
else-if, case, catch-family, and related normalization. Nested callables and
callbacks reset depth because their controls use another `CallableKey`.

The `guards.nesting` section is disabled when omitted or explicitly false.
Enabling it requires a positive JSON integer `reviewAt`; there is no universal
default, FAIL threshold, override, or per-language threshold. Exactly the
threshold passes and greater depth reviews. JSON includes all callable findings
and an optional deterministic deepest line; human output includes only REVIEW.
Only REVIEW routes the stable `nesting` policy ID.

Runner orchestration activates analysis when callable size or nesting is
enabled, constructs facts exactly once, and passes that same immutable value to
each enabled guard. Complexity remains disabled, and scope/exclusion behavior
remains owned by the existing runner rather than introducing issue #16 policy.

## D27 — New guards require evidence-based admission before implementation

After the initial universal guard set, new candidates begin as evaluation issues rather than implementation requests. A candidate must first demonstrate a deterministic anchor, real engineering value, broad applicability, distinct responsibility from mature tooling, stable measurement semantics, actionable/explainable findings, a defensible PASS/REVIEW/FAIL model, and acceptable signal-to-noise on representative code.

Candidates that pass that primary gate must also address threshold/configuration evidence, metric-gaming risk, compatibility with runner-owned scope, architecture/dependency cost, deterministic failure behavior, and portable deterministic tests. For numerical guards, deterministic measurability, engineering usefulness, and universal-default threshold evidence are separate questions; an accepted guard may remain configurable-only.

Every candidate issue ends with one explicit decision: `ACCEPT`, `ACCEPT — CONFIGURABLE ONLY`, `NEEDS MORE EVIDENCE`, or `REJECT / OUT OF SCOPE`. The repository's candidate-guard issue template and `docs/guard-admission.md` define the reusable evidence record.

Once admitted, a guard should normally ship as one complete vertical production slice from deterministic provider/facts through configuration, runner/result/policy integration, tests, CI, and documentation. Internals remain modular, but the project should not accumulate half-integrated production engines that cannot be reached through the normal `code-guard` workflow.

## D28 — Real-project complexity evidence remains Outcome C

Issue #14 sampled 1,132 production files and 11,870 callables across C#, JavaScript, TypeScript/Vue, Python, Go, Rust, and Kotlin at six pinned repository commits. Complexity calculated only from shared production `DecisionFact` values is deterministic and usually review-useful when conditions, loops, catches, ternaries, and executable selection arms dominate.

The real-project evidence changes the earlier provisional concern into two concrete blockers. Counting every short-circuit operator systematically inflates fallback/default and compact predicate code, while opaque lambdas in Kotlin, C#, Python, Go, and Java can hide decisions entirely. These effects make current cross-language values incomparable and do not justify universal or per-language default threshold tables.

Complexity therefore remains **Outcome C** and is not admitted to production yet. No guard, REVIEW default, FAIL state, or runner activation is added. Before renewed admission, a narrow follow-up must test one contribution per maximal boolean expression and close or explicitly bound mainstream lambda ownership. If those semantics become stable, complexity should be an opt-in PASS/REVIEW guard requiring one project-supplied positive `reviewAt`, consuming the runner's single `AnalysisFacts`, and explaining non-zero normalized category counts. Agents may not relax that configuration without authorization.

## D29 — Normalize boolean trees, represent mainstream lambdas, and reject complexity admission

One `short_circuit_boolean` fact represents one maximal connected `&&`/`||` or Python `and`/`or` expression; parentheses are transparent and other expression constructs are boundaries. This removes chain-length weighting while keeping a deterministic syntax-only signal. Kotlin, C#, Go, Java, and expression-only Python anonymous callables now use existing coordinate-qualified callback identities, callable ranges, `CallableKey` ownership, and reset semantics. No fact-model field is added.

The pinned follow-up retained strong outliers and fixed compact-chain inflation, but CogniRelay `applyDetail` remained 28 because its 24 fallback expressions are 24 separate maximal `||` expressions. Syntax cannot distinguish those from genuine single boolean choices without inference or loss of signal. Cyclomatic complexity therefore fails stable-semantics and signal/noise admission and is **REJECT / OUT OF SCOPE**. No production guard, config, default, FAIL state, or vertical implementation issue is authorized.
