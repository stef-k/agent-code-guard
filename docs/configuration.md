# Configuration

Agent Code Guard is designed for zero-config use. Start with the built-in
defaults and add policy only for an immediate project need.

## Discovery and version

By default, Code Guard looks for:

```text
.agent-tools/code-guard.config.json
```

relative to the current working directory. Select another file with
`--config <path>`; an explicitly selected missing file is an error.

The starter convention uses top-level `"version": 1`; the current runtime
accepts that key but does not use it for schema negotiation. A minimal
configuration is:

```json
{
  "version": 1
}
```

## Guard defaults

The six guard keys and their production defaults are:

| Key | Default |
| --- | --- |
| `loc` | `warnAt: 400`, `failAt: 600`, `ratchetAt: "fail"` |
| `callableSize` | `enabled: true`, `reviewAt: 80` |
| `nesting` | `enabled: true`, `reviewAt: 4` |
| `cyclomaticComplexity` | `enabled: true`, `reviewAt: 15` |
| `markdownDocumentSize` | `enabled: true`, `reviewAt: 800` |
| `markdownSectionSize` | `enabled: true`, `reviewAt: 200` |

Every threshold comparison is strict `>`; a value equal to its threshold
passes. The five `reviewAt` guards are REVIEW-only. Only `loc` can FAIL.

Set `enabled` to `false` to disable a guard. For REVIEW-only guards, `reviewAt`
must be a positive integer when enabled. LOC supports its established options,
including `enabled`, `warnAt`, `failAt`, `ratchetAt`, line-count settings, extension policy,
allowed large files, and path-specific overrides.

Example with one deliberate threshold change:

```json
{
  "version": 1,
  "guards": {
    "callableSize": {
      "reviewAt": 100
    }
  }
}
```

## Common scope exclusions

`scope.exclude` removes matching paths before any guard runs:

```json
{
  "version": 1,
  "scope": {
    "exclude": [
      "generated/**"
    ]
  }
}
```

Repeated `--scope-exclude <glob>` values add caller-supplied all-guard
exclusions and compose with project configuration. Only files removed by these
two all-guard forms contribute to the completed result's `excluded` count.

## LOC-specific exclusions

`guards.loc.exclude` applies only to the LOC guard. The repeated CLI option
`--exclude <glob>` adds LOC-only exclusions. These do not remove files from
callable, nesting, complexity, or Markdown analysis, and they do not contribute
to the all-guard `excluded` count. A file skipped only by LOC can still be
`analyzed` by another enabled guard or `inapplicable` when none applies.

```json
{
  "version": 1,
  "guards": {
    "loc": {
      "exclude": [
        "vendor-snapshot/**"
      ]
    }
  }
}
```

Use `scope.exclude` when a path is outside every guard's intended scope. Use
the LOC-specific forms only when the artifact should remain eligible for other
applicable guards.

## Source-controlled LOC ratchet

The allowance data lives only in `.agent-tools/code-guard.loc-baseline.json` at
the owning analysis root. `guards.loc.ratchetAt` controls how that unchanged
version-1 data is interpreted: omitted or `"fail"` records and enforces files
above effective `failAt`; `"review"` starts above effective `warnAt`. Its complete
persisted schema is:

```json
{
  "version": 1,
  "loc": {
    "files": [
      {
        "path": "src/legacy.py",
        "allowedLoc": 749
      }
    ]
  }
}
```

Paths are exact, normalized root-relative `/` paths; allowances are positive
integers. Keys are closed, entries are sorted, and unsupported, malformed,
duplicate, absolute, or unsafe paths fail closed. Writers use UTF-8, two-space
indentation, LF endings, and a final newline.

`--create-loc-baseline` records only selected, applicable files currently
strictly above their effective policy threshold (`failAt` for `fail`, `warnAt`
for `review`), after exclusions, line-count options,
CLI thresholds, and the last matching override. `allowedLargeFiles` entries are
not recorded. `--update-loc-baseline` can only lower or remove existing entries
within its positional bounds; it cannot add or increase one. Normal analysis
never creates, lowers, prunes, or otherwise rewrites this file.

Use exclusions when LOC should not evaluate a file, overrides when the ordinary
project threshold differs, and `allowedLargeFiles` for a reviewed static
exemption. The ratchet instead preserves an exact legacy maximum and rejects
growth; overlap with `allowedLargeFiles` is invalid. Manual ratchet edits require
normal source-control review. This facility is for established repositories,
not new projects, which should meet LOC policy directly. Choose `fail` to freeze
only existing hard failures; choose `review` when established review-level files
must also be non-increasing. Never change the policy, thresholds, exclusions,
exemptions, or stored allowances merely to silence growth.

## Source-controlled Markdown document ratchet

Reviewed document allowances live separately from LOC in
`<analysis-root>/.agent-tools/code-guard.markdown-baseline.json`:

```json
{
  "version": 1,
  "markdownDocumentSize": {
    "files": [
      {
        "path": "docs/architecture.md",
        "allowedLines": 845
      }
    ]
  }
}
```

The version must be integer `1`. Paths are exact, normalized root-relative `/`
paths to `.md` documents (extension matching is case-insensitive); allowances
are positive integer physical-line counts, including blank and comment lines.
Keys are closed, entries must be sorted by path, and duplicate keys or paths,
non-integer values, unsafe/absolute paths, and symlink traversal fail closed.
Writers use UTF-8, two-space indentation, LF endings, and a final newline.
Creation cannot overwrite a baseline; updates replace it atomically only after
all entries in scope have been checked. A no-op update preserves the file.

There are no new guard configuration keys. `markdownDocumentSize.reviewAt`
remains 800 by default and `markdownSectionSize.reviewAt` remains 200.
`guards.loc.ratchetAt` has no effect on Markdown. The document-size guard accepts
an exact-path allowance while the document stays at or below that count;
growth above the allowance reviews whenever it also exceeds `reviewAt`.
Documents at or below `reviewAt` pass without needing a baseline.

`--create-markdown-baseline` records only selected documents above the effective
threshold. `--update-markdown-baseline` only lowers or prunes existing entries
within positional bounds; it never adds or increases allowances. Normal
analysis never mutates this file. Section analysis remains independent, and
section baselines are not supported. These are explicit reviewed-document
acceptances, not default setup or permission to hide growth with exclusions,
threshold changes, or replacement allowances.

See the [workflow and output contract](usage.md#reviewed-markdown-document-ratchet).

## Source-controlled callable-review ratchet

Human-reviewed callable ceilings live independently of LOC and Markdown in
`<analysis-root>/.agent-tools/code-guard.callable-review-baseline.json`:

```json
{
  "version": 1,
  "callableReviews": [
    {
      "path": "offenders_patterns.py",
      "embeddedLanguage": "python",
      "callable": "offenders_patterns._auth",
      "guard": "cyclomaticComplexity",
      "allowedMeasured": 17,
      "reason": "Reviewed cohesive authentication-format catalog; re-review on growth."
    }
  ]
}
```

The schema has closed keys, integer version `1`, and an array of entries. Each
entry requires a safe normalized root-relative physical path with `/`
separators, non-empty embedded language and lexical callable identity, a guard
ID, a positive integer guard-native measurement, and a non-blank human reason.
No range, source hash, ordinal, or alternate measurement field is supported.
Callable size counts physical lines, nesting counts structural depth, and
complexity counts baseline 1 plus normalized decisions, exactly as before.

Canonical persisted/CLI guard IDs are `callableSize`, `nesting`, and
`cyclomaticComplexity`. The last maps explicitly to the existing `complexity`
result/policy ID. `complexity` is rejected in this baseline and acceptance CLI;
it cannot become a separate allowance. Unknown keys/guards, duplicate JSON
properties or exact entries, invalid values/types/reasons, unsafe paths, and
symlink traversal fail closed with exit `3`. Writers sort by path, embedded
language, callable, and guard and use UTF-8, two-space indentation, LF, and a
final newline. Creation and replacement reuse the baseline atomic-write helpers.

The path + embedded language + lexical identity must identify exactly one
callable in the runner's current `AnalysisFacts`. Duplicate lexical identities
are tool errors when an active allowance would match; no duplicate is chosen
by source order or range. Rename, move, disappearance, and movement of a
coordinate-qualified callback can leave a stale entry. Stale entries are
harmless and require explicit pruning; unavailable, excluded, and unselected
files provide no evidence for applying or pruning an existing callable.

There are no new threshold/configuration keys. With ordinary threshold `T`,
accepted value `A`, and current measurement `M`, test `M <= T` first: PASS with
`notNeeded`. Otherwise `M <= A` passes with `withinAllowance`, and `M > A`
reviews with `grown`. Unmatched callables retain ordinary behavior. Threshold
changes never rewrite stored values; disabled guards do not activate because
an allowance exists. LOC and Markdown schemas and lifecycles stay independent.

See the [acceptance and maintenance commands](usage.md#accepted-callable-review-ratchet).

## Fail-closed validation

Malformed JSON, invalid types or thresholds, unknown top-level properties,
unknown guard names, and unknown guard properties are tool errors (exit `3`).
Code Guard does not silently ignore misspelled or unsupported configuration.
Keep configuration small so policy remains visible and reviewable.
