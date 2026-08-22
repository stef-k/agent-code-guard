# Agent Code Guard

Agent Code Guard is a portable set of deterministic guardrails for agent-assisted software development. It is now the canonical implementation of LOC Guard behavior.

It grows out of the lessons learned from [Agent LOC Guard](https://github.com/stef-k/agent-loc-guard): deterministic measurements are useful to coding agents when they act as objective anchors for review, while the agent still applies judgment instead of blindly optimizing a metric.

The project is intentionally narrow. It is not a generic clean-code prompt, IDE replacement, framework analyzer, or security scanner. A guard belongs here only when the underlying concern is broadly meaningful across conventional programming languages and can be measured deterministically.

## Core model

```text
deterministic measurement
        ↓
PASS / REVIEW / FAIL
        ↓
agent interpretation
        ↓
justify, refactor meaningfully, or resolve/escalate
```

The tool detects. The policy interprets. The agent must not game the metric.

## Initial universal guards

The first design targets four cross-language measurements:

1. **File LOC** — physical source-file size, using Agent LOC Guard as the reference implementation and policy prototype.
2. **Callable size** — physical LOC for functions/methods/callables.
3. **Nesting depth** — maximum structural nesting inside a callable.
4. **Cyclomatic complexity** — deterministic execution-path complexity.

Only file LOC currently has mature policy thresholds. Thresholds for callable size, nesting, and complexity must be validated against representative code in multiple languages before becoming defaults.

## Scope rule

A new guard should be added only when all of the following hold:

- it has a deterministic measurement or objective detector;
- the concern is meaningful across languages and frameworks;
- the detector does not depend on the model inventing the measurement;
- a finding gives the agent something genuinely worth inspecting;
- the metric can be used without encouraging mechanical or readability-damaging transformations.

Project-specific architecture boundaries, framework-specific rules, arbitrary style preferences, security scanning, dependency auditing, and similar concerns are outside the universal core.

## Agent-facing architecture

The experience is one skill and one public command, backed by modular internal guards:

```text
one skill
one entry point
one result model
multiple independent guards
```

Detailed guard policies are kept separate so agents load only the policy needed by a triggered finding.

```text
skills/code-guard/
├── SKILL.md
└── references/
    ├── loc-policy.md
    ├── callable-size-policy.md
    ├── nesting-policy.md
    └── complexity-policy.md
```

Expected workflow:

```text
read compact SKILL.md
        ↓
run Code Guard on current changes
        ↓
receive PASS / REVIEW / FAIL findings
        ↓
load only policy files named by triggered findings
        ↓
apply judgment without gaming metrics
```

The machine-readable result exposes required policy identifiers only for actionable guards, for example:

```json
{
  "overall": "review",
  "requiredPolicies": ["complexity"]
}
```

## Universal behavioral rules

These apply to every guard:

- Never game a metric.
- Preserve readability and normal project formatting.
- `REVIEW` requires inspection, not automatic refactoring.
- Refactor only when the result improves real boundaries or clarity.
- Do not create artificial helpers, files, abstractions, or indirection mainly to lower a metric.
- `FAIL` blocks normal completion unless the condition is fixed or an explicitly permitted exception applies.
- Agents must not create or broaden policy exceptions without explicit user approval.
- Normal development checks current changed files; unrelated legacy debt belongs to explicit audit work.

## Changed-code-first

Normal agent use should evaluate the complete current change set relative to `HEAD`:

- staged source changes;
- unstaged source changes;
- untracked non-ignored source files.

Full-repository analysis remains a separate audit mode.

Pull-request CI should evaluate files added or modified by the PR relative to its base rather than unrelated pre-existing oversized files.

## Cross-language requirement

The policy is language-neutral even when deterministic measurement needs language-aware parsing.

Initial feasibility work should prove the common result model across at least:

- Python;
- Go;
- Kotlin;
- C#.

Java and JavaScript/TypeScript are also expected targets. Parser/provider technology should be selected only after the feasibility work; Tree-sitter or language-specific adapters are implementation options, not assumptions.

## Canonical LOC implementation

Agent Code Guard owns LOC behavior. The unified runner supports full audit and the `--changed-only`, `--staged`, `--base-ref <ref>`, `--json`, and `--ci` modes:

```bash
python3 skills/code-guard/scripts/code_guard.py . --changed-only
```

Agent LOC Guard is the completed prototype/reference whose mature behavior at commit `75ab39d261dbc65f78815836fac90add16d265d1` was migrated here, including:

- warning versus hard-failure semantics;
- changed-file scope;
- exclusions and generated files;
- explicit exceptions;
- CI behavior;
- anti-gaming policy;
- agent reasoning around cohesion and meaningful refactoring.

There is no runtime dependency, synchronization layer, or second LOC implementation. Retirement of the prototype repository remains issue #3.

## Result and exit contract

Native LOC states normalize as `ok -> PASS`, `warn -> REVIEW`, `fail -> FAIL`, and `exempt -> PASS` with the exemption reason retained. Only REVIEW and FAIL add `loc` to `requiredPolicies`.

Normal exits are 0 for PASS, 1 for REVIEW, 2 for FAIL, and 3 for configuration/runtime errors. `--ci` changes REVIEW to exit 0; FAIL and errors remain 2 and 3.

## Status

LOC migration complete. Callable size, nesting, complexity, and parser research remain deliberately unimplemented for later issues.

## License

MIT is intended, matching Agent LOC Guard.
