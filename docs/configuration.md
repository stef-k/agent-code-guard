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

## Fail-closed validation

Malformed JSON, invalid types or thresholds, unknown top-level properties,
unknown guard names, and unknown guard properties are tool errors (exit `3`).
Code Guard does not silently ignore misspelled or unsupported configuration.
Keep configuration small so policy remains visible and reviewable.
