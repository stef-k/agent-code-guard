# Markdown Size Review Policy

Use this policy when `markdownDocumentSize` or `markdownSectionSize` appears in
`requiredPolicies`.

A Markdown size REVIEW is an instruction to inspect navigation and
responsibility, not an automatic instruction to split the document or section.
`reviewed; coherent; keep` is a valid outcome for cohesive specifications,
reference material, tables, procedures, and code-heavy sections.

Improve navigation or responsibility boundaries only when the result is
genuinely clearer. Do not add meaningless headings to lower section size,
mechanically split coherent material, compress formatting or remove useful
blank lines, or hide content in fenced code. Agents must not raise thresholds or
disable either guard merely to silence a finding; project or user authority is
required for configuration changes.

## Explicit document acceptance

An explicitly reviewed, cohesive oversized document may use a source-controlled
allowance created with `--create-markdown-baseline`. The separate
`.agent-tools/code-guard.markdown-baseline.json` records exact root-relative paths
and current physical-line counts. Within that allowance the document finding
passes; growth above both the allowance and effective threshold is REVIEW,
never FAIL. At or below the ordinary threshold, an allowance is no longer needed.

This applies only to `markdownDocumentSize`. Inspect section REVIEW findings
independently; document acceptance does not exempt sections. Normal analysis
never changes a baseline. After reductions or deletions,
`--update-markdown-baseline` can explicitly lower or prune existing entries but
cannot add or increase allowances. Agents must not create or replace baselines,
remove allowances, raise thresholds, or add exclusions merely to silence growth.
Baseline acceptance requires explicit authority and source-control review.
