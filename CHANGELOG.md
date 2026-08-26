# Changelog

Notable changes to Agent Code Guard are recorded here.

## Unreleased

### Added

- Zero-baseline CI dogfooding through the installed console command, with visible
  non-blocking REVIEW findings and blocking FAIL findings or tool errors.
- Source-controlled, non-increasing LOC ratchet creation, automatic analysis,
  and explicit lowering/pruning for established legacy repositories.
- Read-only `code-guard doctor` human and JSON diagnostics for the active
  installation, bundled skill, configuration, Git context, and parser providers.
- Compact and explicit debug completed-analysis JSON serialization modes while
  preserving bare `--json` compatibility.
- Deterministic `code-guard --version` reporting from installed distribution
  metadata, with human and JSON output modes.
- Concise selected, analyzed, inapplicable, and all-guard-excluded file counts
  in every completed human and JSON analysis result.
