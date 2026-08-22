# File LOC Policy

File LOC is a deterministic review signal for oversized handwritten source files. It is not a claim that every large file is badly designed.

## Default thresholds

- `<= 400` counted LOC: `PASS`.
- `401–600` counted LOC: `REVIEW`.
- `> 600` counted LOC: `FAIL` by default unless an explicit user-approved exception applies.

Counted LOC and exclusions should follow the mature behavior established by Agent LOC Guard.

## On REVIEW

Inspect:

- whether the file is cohesive;
- whether it has one clear responsibility;
- whether size is mostly straightforward orchestration or linear structure;
- whether separable responsibilities are being mixed;
- likely near-term growth;
- whether splitting would improve real boundaries or merely add indirection.

A warning may be accepted when the file remains cohesive and a split would make the design worse.

## On FAIL

Do not declare normal completion. Either:

- refactor/split the file when that improves the design; or
- obtain explicit approval for a justified exception.

Agents must not self-authorize an exception or alter configuration merely to make the check pass.

## Anti-gaming

Never reduce counted LOC by degrading readability. Do not combine otherwise independent statements/declarations onto fewer lines, minify handwritten code, remove useful comments or structure, or depart from normal project formatting merely to reduce physical line count.

The goal is maintainability, not numeric purity.
