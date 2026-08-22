# Callable Size Policy

Callable size measures the physical LOC of a function, method, constructor, closure, or equivalent callable unit.

This guard exists because a source file can remain modest in size while one operation grows large enough to become difficult to understand or change safely.

## Status

There is no universal review threshold. Projects opt in by supplying
`guards.callableSize.reviewAt`; the guard has no FAIL threshold.

## On REVIEW

Inspect whether the callable:

- performs one coherent operation;
- mixes separable stages or responsibilities;
- contains large regions that have meaningful names and independent contracts;
- has accumulated error handling, branching, transformation, persistence, or orchestration that belongs elsewhere;
- is long mainly because the operation is legitimately linear and easier to understand in one place.

Extract code only when the extracted operation is genuinely cohesive and its name/interface improves comprehension.

REVIEW requires inspection, not automatic refactoring. Examine the callable's
cohesion, responsibility, and growth. Split it only when the resulting design is
clearer, and preserve the project's conventions.

## Anti-gaming

Do not create tiny meaningless helper methods merely to reduce callable LOC. Do not move arbitrary chunks of a procedure behind names such as `ProcessPart1`, `HandleStuff`, or equivalent abstractions that add navigation without improving design.

Do not compress formatting or combine independent statements onto fewer physical lines to lower the measurement.

Do not alter the threshold or disable the guard merely to silence a finding.

A lower callable LOC number is useful only when the resulting code is at least as readable and maintainable as before.
