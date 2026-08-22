# Nesting Depth Policy

Nesting depth measures how deeply control-flow structures are nested within a callable.

This guard exists because deeply nested code can be difficult to reason about even when the file and callable are not especially long.

## Status

Universal default thresholds are not finalized yet. They must be validated across representative code in multiple languages before becoming defaults.

Until then, nesting findings should be treated primarily as `REVIEW` signals under configured or experimental thresholds.

## On REVIEW

Inspect whether the nesting reflects:

- avoidable conditional pyramids;
- loops nested inside branches with additional branching;
- validation/error paths that could be expressed more clearly with guard clauses or early exits;
- multiple responsibilities entangled in one callable;
- state-machine, parser, traversal, or other logic where deeper nesting may be inherent and still readable.

Consider restructuring only when it improves the control-flow model.

## Anti-gaming

Do not flatten code merely to reduce the measured depth if the result becomes harder to follow.

Do not hide nested decisions behind meaningless helper calls or obscure boolean expressions. Do not replace clear structured control flow with clever expressions, compressed conditionals, exception tricks, or other forms whose primary purpose is lowering the metric.

The preferred outcome is clearer control flow, not a smaller number at any cost.
