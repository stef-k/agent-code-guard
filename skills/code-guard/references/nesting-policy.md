# Nesting Depth Policy

Nesting depth measures how deeply control-flow structures are nested within a callable.

This guard exists because deeply nested code can be difficult to reason about even when the file and callable are not especially long.

## Status

The calibrated universal default is REVIEW above structural depth 4. Exactly 4
passes. Authorized project/user configuration may supply a positive
`guards.nesting.reviewAt` override or explicitly disable the guard. The guard
has no FAIL threshold.

## On REVIEW

Inspect whether the nesting reflects:

- avoidable conditional pyramids;
- loops nested inside branches with additional branching;
- validation/error paths that could be expressed more clearly with guard clauses or early exits;
- multiple responsibilities entangled in one callable;
- state-machine, parser, traversal, or other logic where deeper nesting may be inherent and still readable.

REVIEW means inspect control-flow readability; it is not an automatic refactor.
Consider guard clauses or extraction only when they improve clarity. Preserve
idiomatic language and project structure.

## Anti-gaming

Do not flatten code merely to reduce the measured depth if the result becomes harder to follow.

Do not hide nested decisions behind meaningless helper calls or obscure boolean expressions. Do not replace clear structured control flow with clever expressions, compressed conditionals, exception tricks, or other forms whose primary purpose is lowering the metric.

Do not change or disable the configured threshold merely to silence a finding.
Only respect such a change when the project or user has authorized it.

The preferred outcome is clearer control flow, not a smaller number at any cost.
