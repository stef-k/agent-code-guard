# Agent Instructions

## Code Guard

Use the Code Guard skill when creating, modifying, reviewing, or refactoring supported code or Markdown documentation artifacts.

Normal development should check the current changed code and Markdown documentation rather than unrelated legacy files.

With Git, use:

```bash
code-guard . --changed-only
```

Without Git/VCS, pass exactly the files you created or modified; you are responsible for supplying the complete edited-file set:

```bash
code-guard src/Foo.py src/Bar.ts docs/guide.md
```

Do not create a manifest. Specific files inspect those artifacts, a directory or `.` is a deliberate recursive audit, and `--changed-only` requires Git.

Interpret results as:

- `PASS`: no special action.
- `REVIEW`: inspect the finding and load only the policy reference named by the guard.
- `FAIL`: do not declare normal completion until fixed or explicitly excepted with user approval.
- `INCOMPLETE`: preserve and report completed evidence and unavailable paths; do not declare normal completion.

Never game a metric. Preserve readability and project formatting. Do not create artificial helpers, files, abstractions, dense formatting, or configuration exceptions merely to reduce a reported measurement.
