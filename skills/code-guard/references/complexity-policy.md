# Cyclomatic Complexity Policy

Cyclomatic complexity measures the number of independent control-flow paths through a callable.

This guard exists because a callable can be short and only lightly nested while still containing enough branching and decision logic to be difficult to reason about or test safely.

## Status

Complexity is enabled by default. Exactly 15 passes and greater complexity
reviews. It is REVIEW-only and never fails. An authorized project/user positive
integer `reviewAt` may override the default, and explicit disablement is allowed.
Short-circuit booleans deliberately contribute zero. Agents must not weaken or
disable the guard merely to silence findings.

## On REVIEW

Inspect whether complexity comes from:

- many genuinely independent execution paths;
- accumulated conditional branching;
- mixed responsibilities;
- mode/type/state switches that should perhaps be modeled explicitly;
- error handling mixed with core behavior;
- legitimate parsers, protocol handling, state machines, or rule evaluation where branching may be inherent.

Consider refactoring only when the resulting structure makes behavior easier to understand, test, or change.
REVIEW is an inspection request, not an automatic decomposition instruction.

## Anti-gaming

Do not lower complexity by hiding decisions behind meaningless wrappers, opaque boolean expressions, lookup tricks, exception flow, or abstractions whose main purpose is changing the score.

Do not split one coherent decision process into scattered helpers when that makes the execution model harder to follow.

Do not convert clear branches into clever expressions or split coherent parsers,
state machines, and protocol handlers merely to lower the number. Preserve
project and language idioms.

A lower complexity score is not an improvement unless the resulting behavior and structure are clearer.
