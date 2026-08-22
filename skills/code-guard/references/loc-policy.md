# File LOC Policy

This is the canonical Agent Code Guard policy for oversized handwritten source files. LOC is a deterministic review signal, not proof that every large file has poor architecture.

## Core rule

- Up to 400 counted LOC: `PASS`.
- 401 through 600 counted LOC: `REVIEW`.
- More than 600 counted LOC: `FAIL` by default unless an explicit approved exemption applies.
- An existing applicable exemption is `PASS` with native `exempt` status and its reason retained.

Counting and selection follow the canonical runner. By default, LOC is non-blank physical lines and comments count. Normal development uses `--changed-only`: staged, unstaged, and untracked current work relative to `HEAD`. A scan without a selection flag is an explicit full-repository audit.

## REVIEW interpretation

Inspect whether the file remains cohesive and single-responsibility, whether its size is necessary orchestration or linear structure, whether separable responsibilities are mixed, and whether expected near-term growth changes that judgment.

`REVIEW` does not automatically require refactoring. Split only when doing so improves real responsibility boundaries or clarity; accept the warning when the file remains cohesive and a split would add harmful indirection.

Report either `warning accepted with justification: ...` or `split performed because: ...`.

## FAIL and exemptions

For `FAIL`, refactor below the hard cap when that improves the design or obtain explicit user approval for a justified exemption. Otherwise report `hard cap reached; user approval required`.

Existing `allowedLargeFiles` entries may be honored with their configured reasons. Agents must not create, broaden, modify, repurpose, or invent exemptions merely to pass. Threshold overrides are also explicit policy decisions; agents must not create, broaden, or relax them merely to bypass a finding without explicit approval or existing project policy.

Do not infer approval from inconvenience, historical size, a nearby exemption, time pressure, or a request to finish the coding task.

## Do not game LOC

Project formatting conventions take priority. Never combine independent statements, compress control flow or expressions unusually, minify handwritten code, remove useful comments/structure, or fight the formatter merely to lower physical LOC.

Legitimate reductions improve the code: remove redundancy or dead code, simplify control flow, consolidate duplication when appropriate, or split cohesive responsibilities. Prefer cohesive modules over artificial fragmentation.

## Scope discipline

Changed code is evaluated in its resulting form, including a legacy file modified by the task. Unrelated legacy debt belongs to explicit audit work and must not expand a normal change unnecessarily.

Test files may exceed the review threshold when clearly grouped and navigable. They still require explicit approval above the hard cap.
