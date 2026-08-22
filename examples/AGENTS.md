# Agent Instructions

## Code Guard

Use the Code Guard skill when creating, modifying, reviewing, or refactoring handwritten source files.

Normal development should check the current changed source files rather than unrelated legacy files.

When the unified runner is available, use:

```bash
python3 .agent-tools/code_guard.py . --changed-only --config .agent-tools/code-guard.config.json
```

Interpret results as:

- `PASS`: no special action.
- `REVIEW`: inspect the finding and load only the policy reference named by the guard.
- `FAIL`: do not declare normal completion until fixed or explicitly excepted with user approval.

Never game a metric. Preserve readability and project formatting. Do not create artificial helpers, files, abstractions, dense formatting, or configuration exceptions merely to reduce a reported measurement.
