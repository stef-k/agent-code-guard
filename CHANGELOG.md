# Changelog

Notable changes to Agent Code Guard are recorded here.

## Unreleased

### Added

- Non-configurable, Git-mode-only `policyRelaxation` REVIEW comparison of active
  effective configuration and all three baseline families. Source and policy
  share one resolved HEAD/merge-base authority; staged mode uses working-tree
  policy. Typed reasons retain summary counts, 20 details, and an omitted count.
  Invalid/unowned historical authority fails closed; bundled guidance explains
  legitimate authorized relaxation and remaining workflow trust boundaries.
- A separate accepted-REVIEW ratchet shared by callable size, nesting, and
  complexity. Explicit acceptance records one current REVIEW and its reason;
  maintenance only lowers/removes existing ceilings and explicitly prunes stale
  identities. Matching uses unique physical path, embedded language, and lexical
  identity without persisted ranges. Normal checks stay read-only; full/debug
  output explains accepted values, and growth returns the existing guard REVIEW.

### Fixed

- Compare LOC configuration for policy relaxation only when LOC is enabled in
  both policies, keeping dormant maintenance and activation quiet while retaining
  guard-disablement, common-scope, and persisted-baseline detection.

## 0.4.0 - 2026-09-06

### Added

- Explicit source-controlled Markdown document-size ratchets: create accepted
  physical-line allowances and update them only downward or by pruning. Accepted
  documents pass without repeated REVIEW; growth returns REVIEW, while section
  findings remain independent. Normal analysis never writes a baseline.

### Changed

- Give the documentation site a practical introduction, quick start, and agent
  setup guidance, using the shared dark Primer theme. Add GitHub and documentation
  navigation and link the project README directly to the published guides.
- Bundle the updated Markdown ratchet instructions and policy with the skill.

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
