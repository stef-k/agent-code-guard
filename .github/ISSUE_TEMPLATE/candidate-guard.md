---
name: Candidate guard evaluation
about: Evaluate whether a proposed deterministic guard belongs in Agent Code Guard
labels: candidate-guard
---

# Candidate guard: <name>

## Candidate concern

Describe the engineering concern and why it may be worth detecting.

Do **not** assume this candidate belongs in Agent Code Guard. This issue exists to gather evidence and reach an admission decision.

## Proposed deterministic anchor

What exactly would be measured or detected?

- Input/scope:
- Proposed measurement/detector:
- Expected deterministic output:
- Known language/parser differences:

## Primary admission criteria

### 1. Deterministic anchor

Can identical source/configuration produce the same finding without model judgment or unstable external state?

Evidence:

### 2. Engineering value

What real maintainability/readability/design risk does the condition indicate?

Evidence:

### 3. Broad applicability

Which languages/stacks share the underlying concern? What qualifications are language-specific?

Evidence:

### 4. Distinct responsibility

Does this duplicate a mature formatter, compiler, linter, scanner, test tool, dependency tool, or framework analyzer? If related tooling exists, what distinct value would Code Guard provide?

Evidence:

### 5. Stable measurement semantics

Can the measurement have one defensible engineering meaning while preserving necessary language-specific normalization?

Evidence:

### 6. Actionable and explainable findings

What source identity/range/context would a finding expose? Can an agent understand why it triggered without raw AST/parser output?

Evidence:

### 7. Useful state semantics

Which states are justified?

- PASS:
- REVIEW:
- FAIL, if justified:

### 8. Acceptable signal-to-noise

What fixtures and representative real code were sampled? Do findings correspond to conditions actually worth inspecting?

Evidence:

## Production-readiness criteria

### 9. Threshold/config evidence

Separate these questions:

1. Can it be measured deterministically?
2. Is the measurement useful?
3. Is there evidence for a universal default threshold?

Proposed configuration/default policy:

### 10. Gaming resistance

How could an agent game this measurement? Can policy prevent metric-lowering transformations that degrade code quality?

### 11. Scope compatibility

How does it consume the existing runner-owned changed-file / explicit-file / audit scope without inventing another discovery model?

### 12. Architecture fit and cost

Which existing scope, facts/parsing, result, aggregation, packaging, and policy components can be reused? What new dependencies or runtime costs would be introduced?

### 13. Deterministic failure behavior

What happens for unsupported, malformed, incomplete, or otherwise non-authoritative inputs? Is there any heuristic fallback? Why or why not?

### 14. Portable and testable

How will the candidate be tested on supported platforms? Does it require external toolchains or services?

## Research / prototype plan

List only the experiments needed to answer unresolved admission questions. Keep research separate from production implementation.

## Evidence summary

- Synthetic/fixture evidence:
- Representative real-code evidence:
- Cross-language evidence:
- Provider/dependency evidence:
- Known limitations:

## Admission decision

Complete this section before closing the evaluation issue.

```text
Deterministic anchor: PASS / FAIL
Engineering value: PASS / FAIL / UNCLEAR
Broad applicability: PASS / FAIL / QUALIFIED
Distinct responsibility: PASS / FAIL / QUALIFIED
Stable measurement semantics: PASS / FAIL / QUALIFIED
Explainability/actionability: PASS / FAIL / QUALIFIED
State model: PASS / FAIL / QUALIFIED
Signal-to-noise: PASS / FAIL / NEEDS EVIDENCE
Threshold/config evidence: DEFAULT / CONFIGURABLE ONLY / NOT APPLICABLE / UNCLEAR
Gaming risk: ACCEPTABLE / MITIGATED / UNACCEPTABLE
Scope compatibility: PASS / FAIL / QUALIFIED
Architecture fit/cost: PASS / FAIL / QUALIFIED
Failure behavior: PASS / FAIL / QUALIFIED
Portability/testability: PASS / FAIL / QUALIFIED

Decision:
ACCEPT / ACCEPT — CONFIGURABLE ONLY / NEEDS MORE EVIDENCE / REJECT
```

## Vertical implementation slice if accepted

If accepted, describe the smallest complete production slice from deterministic measurement/facts through guard configuration, runner integration, result/policy routing, tests, CI, and documentation.

Do not begin production implementation from this issue until the admission decision is recorded.
