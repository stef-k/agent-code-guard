# Guard Admission and Candidate Evaluation

Agent Code Guard should remain deliberately small. A new guard is not admitted because a metric can be computed; it is admitted only when evidence shows that the concern belongs in the universal deterministic core and can be shipped without weakening the product model.

Candidate evaluation is a separate phase from production implementation. A candidate issue starts from uncertainty and must earn an admission decision. If accepted, the normal next step is one end-to-end vertical implementation slice through measurement/facts, guard behavior, configuration, runner integration, results, policy, tests, documentation, and CI.

## Primary admission criteria

The first eight questions decide whether a candidate fundamentally belongs in Agent Code Guard. A material failure here should usually stop the proposal before production design work.

### 1. Deterministic anchor

Can the condition be measured or detected objectively so the same source and configuration produce the same result?

The trigger must not depend on model judgment, network state, timing, popularity, or other unstable external context. The model may interpret a finding after detection; it must not invent the measurement that triggers its own review.

### 2. Engineering value

Does the condition correlate with a real maintainability, readability, cohesion, control-flow, or design concern worth making an agent inspect?

A measurable property is not automatically useful. The candidate should identify code that a competent developer would plausibly want to review.

### 3. Broad applicability

Is the underlying concern meaningful across a useful range of conventional languages and stacks?

Language-specific parsing and normalization are acceptable implementation details. Framework-specific policy, organization-specific architecture rules, or narrow style preferences normally do not belong in the universal core.

### 4. Distinct responsibility

Does Agent Code Guard add meaningful value rather than duplicating a mature project tool poorly?

Formatters, compilers, linters, test runners, security scanners, dependency tools, accessibility tools, and framework analyzers should remain authoritative for concerns they already solve well unless Code Guard has a clearly distinct agent-oriented reason to participate.

### 5. Stable measurement semantics

Can the project define precisely what is being measured across supported languages without hiding important semantic differences?

A normalized common core may coexist with language-specific provider kinds or adapters. The admission question is whether the resulting measurement still has a stable engineering meaning.

### 6. Actionable and explainable findings

Can a finding identify the relevant source location or construct and explain the trigger well enough for an agent or developer to inspect it?

A bare score with no useful location or interpretation is weak evidence for admission. Findings should expose normalized context, not raw parser internals.

### 7. Useful state semantics

Can the candidate support meaningful PASS / REVIEW / FAIL behavior?

A guard does not need every state. PASS/REVIEW-only is valid and should be preferred when hard failure is not strongly justified. FAIL requires substantially stronger evidence because it blocks normal completion.

### 8. Acceptable signal-to-noise

On representative code, does the candidate identify conditions worth inspecting without producing routine or overwhelming noise?

Synthetic fixtures prove determinism, not usefulness. Where signal quality is uncertain, sample representative real code before admission.

## Production-readiness criteria

A candidate that passes the primary gate must also answer the following before or during its production design.

### 9. Threshold and configuration evidence

If the guard is numerical, is there evidence for a universal default threshold?

If not, can the guard remain explicitly configurable rather than inventing a default? Measurement validity, engineering usefulness, and default-threshold validity are separate questions.

### 10. Gaming resistance

Can an agent lower the metric while making the code worse?

If so, can policy and finding semantics constrain that behavior adequately? A candidate is unsuitable when its natural optimization path strongly rewards unreadable, fragmented, compressed, or otherwise degraded code.

### 11. Scope compatibility

Does the guard fit the existing runner-owned changed-file, explicit-file, and audit scope model?

A guard should not normally introduce independent file discovery, VCS logic, ignore handling, or a parallel scope model.

### 12. Architecture fit and cost

Can the candidate reuse existing scope, shared facts/parsing, result aggregation, packaging, policy routing, and CLI infrastructure where appropriate?

New dependencies, parser backends, or runtime costs must be proportionate to the value of the guard. A feature that requires a broad core redesign needs stronger evidence than one that fits existing seams.

### 13. Deterministic failure behavior

When authoritative measurement is impossible, can the tool fail clearly rather than silently skip, guess, or fall back to heuristics?

Unsupported inputs may be explicitly inapplicable. Supported inputs that cannot be measured authoritatively should produce deterministic tool errors according to the product contract.

### 14. Portable and testable

Can the guard be exercised deterministically in fixtures and CI on the project's supported platforms without unreasonable external toolchains or environment assumptions?

Cross-platform packaging and runtime behavior must be understood before the guard is considered production-ready.

## Candidate lifecycle

Use the following process for future proposals:

```text
new candidate idea
    -> open a Candidate guard issue
    -> evaluate primary admission criteria
    -> prototype / sample representative code where evidence is missing
    -> evaluate production-readiness criteria
    -> record an admission decision
       -> ACCEPT
       -> ACCEPT — CONFIGURABLE ONLY
       -> NEEDS MORE EVIDENCE
       -> REJECT / OUT OF SCOPE
    -> if accepted, open one vertical production implementation slice
```

The evaluation issue must not assume acceptance. Its purpose is to test the idea against the project boundary.

## Separate the three numerical questions

For metric-based candidates, always answer these independently:

1. **Can we measure it deterministically?**
2. **Is the measurement useful enough to act as a review anchor?**
3. **Can we justify a default threshold?**

A candidate may pass the first two and still require project-supplied configuration. That is a valid outcome and is preferable to inventing a universal threshold.

## Required admission decision

Every candidate issue should end with a compact decision record using this structure:

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

If accepted, the issue should also state the proposed vertical implementation boundary and any evidence that must remain explicit as a qualification.

## Production delivery after admission

Once a candidate is accepted, delivery should normally be vertical even though the internals remain modular:

```text
deterministic provider / facts if needed
    -> guard calculation
    -> configuration
    -> shared runner orchestration
    -> PASS / REVIEW / FAIL aggregation
    -> JSON and human findings
    -> requiredPolicies routing
    -> agent policy
    -> tests and cross-platform CI
    -> documentation
```

Do not accumulate half-integrated production engines that users or agents cannot reach through the normal `code-guard` command. A separate infrastructure slice is justified only when it is independently valuable or when evidence shows the feature is too large to land safely as one vertical change.
