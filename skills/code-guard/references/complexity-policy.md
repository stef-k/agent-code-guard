# Cyclomatic Complexity Policy

Cyclomatic complexity measures the number of independent control-flow paths through a callable.

This guard exists because a callable can be short and only lightly nested while still containing enough branching and decision logic to be difficult to reason about or test safely.

## Status

Issue #25 accepted complexity as configurable-only after zero short-circuit
weighting preserved strong review signals and removed boolean-expression noise.
The guard is not implemented yet, so this policy is research-only and cannot be
requested through current `requiredPolicies`. A future opt-in guard must require
a project-supplied positive `reviewAt`, provide PASS/REVIEW only, and have no
universal or per-language default.

## On REVIEW

Inspect whether complexity comes from:

- many genuinely independent execution paths;
- accumulated conditional branching;
- mixed responsibilities;
- mode/type/state switches that should perhaps be modeled explicitly;
- error handling mixed with core behavior;
- legitimate parsers, protocol handling, state machines, or rule evaluation where branching may be inherent.

Consider refactoring only when the resulting structure makes behavior easier to understand, test, or change.

## Anti-gaming

Do not lower complexity by hiding decisions behind meaningless wrappers, opaque boolean expressions, lookup tricks, exception flow, or abstractions whose main purpose is changing the score.

Do not split one coherent decision process into scattered helpers when that makes the execution model harder to follow.

A lower complexity score is not an improvement unless the resulting behavior and structure are clearer.
