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
