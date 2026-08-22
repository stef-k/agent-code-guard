# Agent Instructions

## Code Guard

Use the Code Guard skill when creating, modifying, reviewing, or refactoring handwritten source files.

Normal development should check the current changed source files rather than unrelated legacy files.

With Git, use:

```bash
code-guard . --changed-only --config .agent-tools/code-guard.config.json
```

Without Git/VCS, pass exactly the files you created or modified; you are responsible for supplying the complete edited-file set:

```bash
code-guard src/Foo.py src/Bar.ts tests/FooTests.cs --config .agent-tools/code-guard.config.json
```

Do not create a manifest. Specific files inspect those artifacts, a directory or `.` is a deliberate recursive audit, and `--changed-only` requires Git.

Interpret results as:

- `PASS`: no special action.
- `REVIEW`: inspect the finding and load only the policy reference named by the guard.
- `FAIL`: do not declare normal completion until fixed or explicitly excepted with user approval.

Never game a metric. Preserve readability and project formatting. Do not create artificial helpers, files, abstractions, dense formatting, or configuration exceptions merely to reduce a reported measurement.
