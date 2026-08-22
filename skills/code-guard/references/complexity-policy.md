# Cyclomatic Complexity Policy

Cyclomatic complexity measures the number of independent control-flow paths through a callable.

This guard exists because a callable can be short and only lightly nested while still containing enough branching and decision logic to be difficult to reason about or test safely.

## Status

Universal default thresholds are not finalized yet. They must be validated against representative code in multiple languages before becoming defaults.

Issue #14 retained Outcome C: production complexity remains disabled while
short-circuit normalization and opaque lambda ownership are unsettled. During
research, values are `REVIEW` anchors only; no universal or FAIL threshold is
authorized.

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
