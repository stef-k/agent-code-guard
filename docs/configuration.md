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
| `loc` | `warnAt: 400`, `failAt: 600` |
| `callableSize` | `enabled: true`, `reviewAt: 80` |
| `nesting` | `enabled: true`, `reviewAt: 4` |
| `cyclomaticComplexity` | `enabled: true`, `reviewAt: 15` |
| `markdownDocumentSize` | `enabled: true`, `reviewAt: 800` |
| `markdownSectionSize` | `enabled: true`, `reviewAt: 200` |

Every threshold comparison is strict `>`; a value equal to its threshold
passes. The five `reviewAt` guards are REVIEW-only. Only `loc` can FAIL.

Set `enabled` to `false` to disable a guard. For REVIEW-only guards, `reviewAt`
must be a positive integer when enabled. LOC supports its established options,
including `enabled`, `warnAt`, `failAt`, line-count settings, extension policy,
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

The legacy-adoption ratchet is not a configuration property. Its only location
is `.agent-tools/code-guard.loc-baseline.json` at the owning analysis root, and
its complete version-1 schema is:

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
strictly above their effective `failAt`, after exclusions, line-count options,
CLI thresholds, and the last matching override. `allowedLargeFiles` entries are
not recorded. `--update-loc-baseline` can only lower or remove existing entries
within its positional bounds; it cannot add or increase one. Normal analysis
never creates, lowers, prunes, or otherwise rewrites this file.

Use exclusions when LOC should not evaluate a file, overrides when the ordinary
project threshold differs, and `allowedLargeFiles` for a reviewed static
exemption. The ratchet instead preserves an exact legacy maximum and rejects
growth; overlap with `allowedLargeFiles` is invalid. Manual ratchet edits require
normal source-control review. This facility is for established repositories,
not new projects, which should meet LOC policy directly.

## Fail-closed validation

Malformed JSON, invalid types or thresholds, unknown top-level properties,
unknown guard names, and unknown guard properties are tool errors (exit `3`).
Code Guard does not silently ignore misspelled or unsupported configuration.
Keep configuration small so policy remains visible and reviewable.
