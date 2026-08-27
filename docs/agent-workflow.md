# Human and agent workflow

This guide owns the repeated-use workflow for Agent Code Guard. The
[usage guide](usage.md) remains the CLI reference, and
[skill distribution](skill-distribution.md) explains skill discovery and
activation.

## Human setup and decisions

Install the published command in an isolated environment and verify the active
installation:

```bash
pipx install agent-code-guard
code-guard --version
code-guard doctor
```

Ask your coding agent to locate the bundled version-matched skill with
`code-guard --skill-path` and adopt the workflow below without creating a LOC
baseline. Decide whether checks remain manual or use an optional platform hook.
Exporting a skill into a persistent directory, installing a hook, or changing
persistent user or repository configuration requires your authorization.

Require the agent to report its final result and any REVIEW findings it accepts
with justification. Use CI as the final gate, not as a substitute for checks
during development.

## The shared loop

```text
edit supported code or Markdown
        ↓
run Code Guard on changed scope
        ↓
PASS → continue
REVIEW → inspect, justify or genuinely improve
FAIL → fix or obtain an explicitly authorized exception
        ↓
rerun
        ↓
report the result before completion
```

After each meaningful turn that changes supported source code or Markdown, the
agent runs Code Guard. It inspects every REVIEW and FAIL, loads only policies
named by the result, and refactors only when doing so improves real structure.
It must never split code mechanically or weaken thresholds, exclusions,
configuration, or baselines to silence a measurement. After relevant
corrections it reruns the check, and it always runs a final check before
declaring completion.

PASS means continue. REVIEW means inspect and either make a genuine improvement
or retain the code with an honest justification; it is not automatically a
defect. FAIL blocks normal completion until corrected or covered by an
explicitly authorized policy exception. Tool or invocation errors mean the
analysis did not complete.

## Manual agent loop

In a Git repository, prefer changed-work scope and compact JSON when structured,
low-noise output helps:

```bash
code-guard . --changed-only --json --json-mode compact
```

Git supplies staged, unstaged, and untracked candidates within the positional
bounds. The process exits are exact:

- PASS: `0`
- REVIEW: `1`
- FAIL: `2`
- tool or invocation error: `3`

The agent inspects REVIEW and FAIL findings, applies judgment, loads only the
named required policies, and reruns after relevant correction.

Git selection requires a Git repository and fails instead of silently becoming
a recursive audit. Outside Git, pass the exact edited files:

```bash
code-guard path/to/edited.py docs/edited.md --json --json-mode compact
```

Do not recursively scan the whole tree after every turn.

## Optional hook-assisted loop

Agent Code Guard does not install or manage hooks. If the coding-agent platform
supports a post-edit or post-turn hook, and the user authorizes the persistent
configuration change, that platform may invoke:

```bash
code-guard . --changed-only --ci --json --json-mode compact
```

`--ci` changes only REVIEW's process exit from `1` to `0`. REVIEW findings
remain visible and require inspection; FAIL remains `2`, and tool or invocation
errors remain `3`. Hook output must not be suppressed.

Hook syntax and configuration paths are platform-specific. The agent must
consult its platform's own documentation; no universal hook configuration is
implied. Outside Git, the integration must supply the exact edited files.

## Completion and CI

Before completion, rerun Code Guard on the complete changed scope. Report the
aggregate result, any FAIL or tool errors, and each accepted REVIEW with its
reason. Then use the repository's CI integration as the final gate. Humans
remain responsible for deciding whether accepted REVIEW pressure warrants
follow-up work and for authorizing exceptions or persistent integrations.
