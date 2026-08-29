# Changelog

Notable changes to Agent Code Guard are recorded here.

## Unreleased

## 0.3.1 - 2026-08-29

### Changed

- Reuse one immutable invocation context for configuration and canonical selected-file identities during ordinary multi-guard analysis, and use shared source line indexes for constant-time syntax location mapping.
- Add a reproducible, non-CI Wayfarer benchmark harness for LOC-only, syntax-only, normal, and profiled scans.

### Fixed

- Restore fresh physical containment validation for baseline-enabled analysis and make benchmark output and Git-status verification fail closed.

## 0.3.0 - 2026-08-28

### Added

- Opt-in `guards.loc.ratchetAt: "review"` support freezes source-controlled LOC
  allowances beginning above the effective review threshold, while omitted or
  explicit `"fail"` preserves the existing failure-only lifecycle and output.

### Fixed

- Known per-file syntax and provider failures now produce blocking structured
  incomplete results while preserving independent LOC, Markdown, and unaffected
  syntax evidence; completed output remains schema- and byte-compatible.
- Valid C# that uses `async` as an expression identifier or named-argument name
  now receives a narrow, coordinate-preserving parser compatibility retry while
  unknown, ambiguous, and malformed syntax still fails closed.

## 0.2.0 - 2026-08-27

### Added

- Zero-baseline CI dogfooding through the installed console command, with no
  baseline for this repository, visible non-blocking REVIEW findings under
  `--ci`, and blocking FAIL findings or tool errors.
- Source-controlled, non-increasing LOC ratchet creation, automatic read-only
  analysis, and explicit lowering/pruning for established legacy repositories;
  new projects and this repository should use a zero baseline.
- Read-only `code-guard doctor` human and JSON diagnostics for the active
  installation, bundled skill, configuration, Git context, and parser providers.
- Compact and explicit debug completed-analysis JSON serialization modes:
  bare `--json` remains the compatible full form, debug is byte-identical for
  the same completed invocation, and compact removes only normalized pass
  findings while preserving actionable findings and result structure.
- Deterministic `code-guard --version` reporting from installed distribution
  metadata, with human and JSON output modes.
- Concise selected, analyzed, inapplicable, and all-guard-excluded file counts
  in every completed human and JSON analysis result, where analyzed plus
  inapplicable equals selected and excluded files are disjoint.
