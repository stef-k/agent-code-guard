# Callable Size Policy

Callable size measures the physical LOC of a function, method, constructor, closure, or equivalent callable unit.

This guard exists because a source file can remain modest in size while one operation grows large enough to become difficult to understand or change safely.

## Status

Default thresholds are not finalized yet. They must be validated against representative code in multiple languages before becoming universal defaults.

Until then, callable-size findings should be treated primarily as `REVIEW` signals under configured or experimental thresholds.

## On REVIEW

Inspect whether the callable:

- performs one coherent operation;
- mixes separable stages or responsibilities;
- contains large regions that have meaningful names and independent contracts;
- has accumulated error handling, branching, transformation, persistence, or orchestration that belongs elsewhere;
- is long mainly because the operation is legitimately linear and easier to understand in one place.

Extract code only when the extracted operation is genuinely cohesive and its name/interface improves comprehension.

## Anti-gaming

Do not create tiny meaningless helper methods merely to reduce callable LOC. Do not move arbitrary chunks of a procedure behind names such as `ProcessPart1`, `HandleStuff`, or equivalent abstractions that add navigation without improving design.

Do not compress formatting or combine independent statements onto fewer physical lines to lower the measurement.

A lower callable LOC number is useful only when the resulting code is at least as readable and maintainable as before.
