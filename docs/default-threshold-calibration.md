# Default Threshold Calibration

## 1. Executive conclusion

Agent Code Guard should use these conservative universal REVIEW defaults:

| Guard | Built-in `reviewAt` | Enabled when omitted? | Result above threshold |
|---|---:|---|---|
| Callable physical LOC | 80 | Yes | REVIEW only |
| Structural nesting | 4 | Yes | REVIEW only |
| Cyclomatic complexity | 15 | Yes, once #27 ships | REVIEW only |

Exactly the threshold passes. A greater measurement reviews. Projects and users
may override a built-in with a positive JSON integer or explicitly disable a
guard. These values are inspection triggers, not claims that code becomes bad at
one exact number.

This calibration PR does not activate the defaults in production. Default
activation for the existing callable-size and nesting guards changes ordinary
runner parsing and error behavior and belongs in a focused implementation issue.
Issue #27 owns the complete complexity production slice and must implement 15.

## 2. Product philosophy

Defaults are pragmatic universal guardrails, not mathematical laws. A REVIEW
asks whether the measured unit is still coherent and readable; it does not
command decomposition. The desired intervention point leaves ordinary code
alone, catches the costly tail, and remains useful even when inspection concludes
that the current design is appropriate.

File LOC is the precedent. More than 400 lines reviews because navigation,
cohesion, and local reasoning may be costly; more than 600 fails because the
source unit is exceptionally large. Those values are practical policy, not
statistical proof. This issue retains LOC 400/600 unchanged.

## 3. Methodology

Three independent evidence sources were combined:

1. The exact pinned #14/#25 corpus was measured using current #26 production
   `AnalysisFacts`. Callable size is inclusive physical source-range LOC;
   nesting is normalized executable depth; complexity is one plus normalized
   decisions owned by one `CallableKey`.
2. A small candidate set was derived from the distributions and mature-tool
   precedent. Review rates use strict `measurement > reviewAt`.
3. Real callables below, at, above, and far above serious candidates were read.
   Both useful findings and cases that should probably remain unchanged were
   recorded.

Percentiles use deterministic nearest rank, except median (the conventional
middle or mean of the two middle values). P99 is omitted where fewer than 100
callables make it unhelpful. Distribution informs the decision but does not
choose it mechanically, and rates are not normalized by language.

The durable sampler is `research/default_threshold_sample.py`. A representative
invocation is:

```powershell
$env:PYTHONPATH='<agent-code-guard>;<agent-code-guard>\src'
python <agent-code-guard>\research\default_threshold_sample.py <production-roots> --candidate callableSize=60 --candidate callableSize=80 --candidate callableSize=100 --candidate callableSize=120 --candidate nesting=4 --candidate nesting=5 --candidate nesting=6 --candidate complexity=10 --candidate complexity=12 --candidate complexity=15 --candidate complexity=20 --output <outside-repository.json>
```

Production roots excluded tests, benchmarks, generated migrations/fixtures,
build output, vendored dependencies, minified assets, and the parser-inapplicable
paths already recorded by #25. Raw callable rows were used only for inspection
and were deleted after summarization.

## 4. Pinned corpus

| Project | Commit | Production scope | Supported files | Callables/languages |
|---|---|---|---:|---|
| Wayfarer | `d4ae7142cfabb50e33fb8d28bf8266b170009f37` | production roots; excludes tests, migrations, tools, coverage, vendored/minified/build output and the recorded rejected KML parser | 460 | 3,980 C#; 1,348 JavaScript; 1,289 TypeScript/Vue |
| CogniRelay | `945d179366b9b6fa6a2ba4e4d386c349bbdbe210` | `app`, `cognirelay`, `setup.py`; excludes tests, tools, agent assets | 85 | 1,319 Python; 28 JavaScript |
| xrplnsapi | `ed1175be0415bb193db41ca174387a9cacb41652` | complete production source | 13 | 18 Go |
| WayfarerMobile | `0162d373026eb5caea337f8c8f76c31328d167e7` | `src`; excludes embedded Quill and two recorded parser-rejected files | 299 | 2,925 C# |
| ripgrep | `3fce3b5bb0236da2df6d99672afb8a719642eca7` | `crates`, root `build.rs`; excludes tests, benches, fuzz | 90 | 3,219 Rust |
| nowinandroid | `7d45eae4f8720a0c77f507712ba2437ff974b6ed` | app/core/feature/sync production roots; excludes tests, benchmarks, generated fixtures, design-system and screenshot-tooling parser gaps | 185 | 1,237 Kotlin in this current-facts run |

The nowinandroid file selection is the same 185-file pinned selection recorded
by #26, but current extraction produced 1,237 callables rather than the earlier
1,197. The 40-callable difference is retained as a reproducibility qualification,
not hidden. It is confined to the low tail: no added callable exceeds nesting 4
or complexity 10, and it changes only the callable-size denominator slightly.

Run the command above from each pinned clone root with these exact middle
arguments (the common candidate suffix remains unchanged):

| Project | Roots and exclusions |
|---|---|
| Wayfarer | `. --exclude 'tests/**' --exclude 'Migrations/**' --exclude 'tools/**' --exclude 'coverage/**' --exclude 'wwwroot/lib/**' --exclude '**/*.min.js' --exclude '**/bin/**' --exclude '**/obj/**' --exclude 'Parsers/WayfarerKmlParser.cs'` |
| CogniRelay | `app cognirelay setup.py --exclude '**/tests/**' --exclude '**/test/**' --exclude 'tools/**' --exclude '**/.agent-tools/**' --exclude '**/.claude/**'` |
| xrplnsapi | `. --exclude '**/*_test.go'` |
| WayfarerMobile | `src --exclude '**/Resources/Raw/quill/**' --exclude 'src/WayfarerMobile/MauiProgram.cs' --exclude 'src/WayfarerMobile/Handlers/CustomWebViewHandler.cs' --exclude '**/bin/**' --exclude '**/obj/**'` |
| ripgrep | `crates build.rs --exclude '**/tests/**' --exclude '**/test/**' --exclude '**/benches/**' --exclude '**/bench/**' --exclude '**/fuzz/**'` |
| nowinandroid | `app app-nia-catalog core feature sync --exclude '**/src/test/**' --exclude '**/src/androidTest/**' --exclude '**/src/testFixtures/**' --exclude '**/benchmark/**' --exclude '**/benchmarks/**' --exclude 'core/designsystem/**' --exclude 'core/screenshot-testing/**'` |

## 5. External-tool precedent

| Tool | Comparable rule | Documented threshold | Activation / severity | Important difference |
|---|---|---:|---|---|
| [ESLint](https://eslint.org/docs/latest/rules/max-lines-per-function) | `max-lines-per-function` | 50 | opt-in, configurable | full function span by default; blank/comment handling is configurable |
| [detekt](https://detekt.dev/docs/next/rules/complexity/#longmethod) | `LongMethod` | 60 | active by default, configurable | Kotlin-specific line semantics |
| [Checkstyle](https://checkstyle.org/checks/sizes/methodlength.html) | `MethodLength` | 150 | configured module; error severity by default | Java-only and includes empty/comment lines by default |
| [ESLint](https://eslint.org/docs/latest/rules/max-depth) | `max-depth` | 4 | opt-in, configurable | JavaScript block depth is not identical to normalized executable depth |
| [detekt](https://detekt.dev/docs/next/rules/complexity/#nestedblockdepth) | `NestedBlockDepth` | 4 | active by default, configurable | Kotlin block-depth semantics |
| [Checkstyle](https://checkstyle.org/checks/coding/nestedifdepth.html) | `NestedIfDepth` | 1 | configured module; error severity by default | counts nested if/else only, so the number is not comparable |
| [Ruff](https://docs.astral.sh/ruff/settings/#lint-mccabe-max-complexity) | McCabe C901 | 10 | rule opt-in; configurable | Python-specific construct coverage |
| [Checkstyle](https://checkstyle.org/checks/metrics/cyclomaticcomplexity.html) | `CyclomaticComplexity` | 10 | configured module; error severity by default | counts `&&`/`||`; switch handling is configurable |
| [detekt](https://detekt.dev/docs/next/rules/complexity/#cyclomaticcomplexmethod) | `CyclomaticComplexMethod` | 14 | active by default, configurable | counts booleans, Elvis, jumps and Kotlin scope functions |
| [ESLint](https://eslint.org/docs/latest/rules/complexity) | `complexity` | 20 | opt-in, configurable | counts booleans, optional chains, defaults and logical assignment |
| [PMD Apex](https://pmd.github.io/pmd/pmd_rules_apex_design.html#cyclomaticcomplexity) | `CyclomaticComplexity` | 10 per method | configurable, medium priority | Apex-specific and counts boolean subexpressions |

Precedent establishes useful orders of magnitude and shows that threshold and
activation are separate choices. It does not supply Code Guard's values.
Complexity comparisons are especially loose because Code Guard deliberately
does not count short-circuit booleans, fallback/null-aware constructs, optional
navigation, or Kotlin Elvis.

## 6. Callable-size distributions

Values are `median / P75 / P90 / P95 / P99 / maximum`.

| Project / language | n | Physical LOC distribution |
|---|---:|---|
| Wayfarer / C# | 3,980 | 1 / 11 / 30 / 48 / 112 / 414 |
| Wayfarer / JavaScript | 1,348 | 6 / 17 / 38 / 63 / 148 / 1,740 |
| Wayfarer / TypeScript/Vue | 1,289 | 3 / 9 / 17 / 27 / 90 / 207 |
| CogniRelay / Python | 1,319 | 11 / 24 / 63 / 109 / 213 / 890 |
| CogniRelay / JavaScript | 28 | 7.5 / 17 / 35 / 77 / — / 274 |
| xrplnsapi / Go | 18 | 15.5 / 27 / 45 / 66 / — / 66 |
| WayfarerMobile / C# | 2,925 | 7 / 17 / 37 / 53 / 95 / 177 |
| ripgrep / Rust | 3,219 | 5 / 13 / 24 / 35 / 69 / 220 |
| nowinandroid / Kotlin | 1,237 | 4 / 12 / 24 / 38 / 80 / 316 |

## 7. Callable-size candidates

External precedent and the corpus justified 60, 80, 100, and 120 as the only
serious candidates. Aggregate rates over 15,363 callables were:

| `reviewAt` | REVIEW count | Rate | Assessment |
|---:|---:|---:|---|
| 60 | 534 | 3.48% | defensible but catches more coherent medium functions than needed for a universal default |
| 80 | 310 | 2.02% | conservative tail intervention with useful boundary findings |
| 100 | 198 | 1.29% | useful, but misses several functions already costly enough to inspect |
| 120 | 130 | 0.85% | too tolerant for a navigation/cohesion guardrail |

Per-language rates for 60 / 80 / 100 / 120 were: Wayfarer C# 3.27 / 1.98 /
1.26 / 0.93%; Wayfarer JavaScript 5.12 / 3.26 / 1.78 / 1.41%; Wayfarer
TypeScript/Vue 1.24 / 1.16 / 0.78 / 0.47%; CogniRelay Python 10.31 / 7.05 /
5.69 / 3.87%; CogniRelay JavaScript 7.14 / 3.57 / 3.57 / 3.57%; xrplnsapi Go
5.56 / 0 / 0 / 0%; WayfarerMobile C# 3.56 / 1.61 / 0.79 / 0.24%; ripgrep
Rust 1.52 / 0.59 / 0.25 / 0.12%; and nowinandroid Kotlin 2.18 / 0.97 /
0.57 / 0.40%. The shared threshold intentionally does not equalize these rates.

## 8. Callable-size boundary inspection

| Candidate | Below | At/around | Moderately above | Major outlier |
|---:|---|---|---|---|
| 60 | nowinandroid `ForYouScreen.kt:258 onboarding` 59 | CogniRelay `app/context/service.py:551 _raw_scan_recent_relevant` 60 | Wayfarer `SettingsController.cs:462 NormalizeTileProviderSettings` 75 | Wayfarer `Trip/Index.js:10 <callback>` 1,740 |
| 80 | ripgrep `literal.rs:895 queries` 79 | nowinandroid `MainActivity.kt:78 onCreate` 80 | Wayfarer `GroupsController.cs:100 Latest` 95 | CogniRelay `app/discovery/service.py:193 tool_catalog` 890 |
| 100 | Wayfarer `segmentRouteProposalState.ts:28 createSegmentRouteProposalStore` 99 | Wayfarer `Program.cs:674 ConfigureMiddleware` 100 | Wayfarer `TileCacheService.cs:1880 PurgeLRUCacheAsync` 115 | nowinandroid `Catalog.kt:58 NiaCatalog` 316 |
| 120 | Wayfarer `Timeline/Index.js:647 generateStatsModalContent` 119 | WayfarerMobile `SseClient.cs:324 ConnectAndStreamAsync` 120 | Wayfarer `BulkEditNotes.js:4 <callback>` 139 | ripgrep `hiargs.rs:114 HiArgs::from_low_args` 220 |

At the selected boundary, additional 81–82-line examples were Wayfarer
`TripController.Create` (authorization, persistence, and shadow-region flow),
CogniRelay `shared_create_service` (coherent validation and persistence),
WayfarerMobile `SegmentAnchorResolver.Resolve` (many sequential validations),
and ripgrep `is_readable_stdin` (readable platform/error handling). The last is
a useful noise example: inspection can reasonably conclude “keep.” At 60,
ordinary coherent units appear too often; at 100 and 120, already costly units
such as `Latest` and `PurgeLRUCacheAsync` escape review.

## 9. Callable-size final decision

Use `reviewAt: 80` and enable the guard by default. Sixty is unnecessarily eager
for a universal policy; 100 and 120 allow several already-burdensome logical
units through. A coherent 81-line callable may remain unchanged: the finding
asks about navigation, local comprehension, and responsibility, not a score.

## 10. Nesting distributions

| Project / language | n | median / P75 / P90 / P95 / P99 / max |
|---|---:|---|
| Wayfarer / C# | 3,980 | 0 / 0 / 1 / 2 / 3 / 7 |
| Wayfarer / JavaScript | 1,348 | 0 / 1 / 2 / 2 / 3 / 5 |
| Wayfarer / TypeScript/Vue | 1,289 | 0 / 1 / 1 / 1 / 2 / 5 |
| CogniRelay / Python | 1,319 | 1 / 2 / 3 / 4 / 5 / 8 |
| CogniRelay / JavaScript | 28 | 1 / 1 / 1 / 1 / — / 1 |
| xrplnsapi / Go | 18 | 1 / 2 / 4 / 4 / — / 4 |
| WayfarerMobile / C# | 2,925 | 0 / 1 / 2 / 2 / 3 / 5 |
| ripgrep / Rust | 3,219 | 0 / 0 / 1 / 2 / 3 / 5 |
| nowinandroid / Kotlin | 1,237 | 0 / 0 / 0 / 1 / 1 / 3 |

## 11. Nesting candidates

| `reviewAt` | REVIEW count | Rate | Assessment |
|---:|---:|---:|---|
| 4 | 49 | 0.32% | depth 5 means five simultaneous executable contexts; findings are sparse and useful |
| 5 | 16 | 0.10% | misses several worthwhile depth-5 inspections |
| 6 | 6 | 0.04% | effectively an extreme-outlier detector |

At 4 / 5 / 6, rates were: Wayfarer C# 0.23 / 0.10 / 0.05%; Wayfarer
JavaScript 0.22 / 0 / 0%; Wayfarer TypeScript/Vue 0.08 / 0 / 0%; CogniRelay
Python 2.27 / 0.91 / 0.30%; WayfarerMobile C# 0.10 / 0 / 0%; ripgrep Rust
0.09 / 0 / 0%; and zero for the other sampled groups.

## 12. Nesting boundary inspection

| Candidate | Below | At/around | Moderately above | Major outlier |
|---:|---|---|---|---|
| 4 | CogniRelay `artifact_lifecycle/service.py:538 externalize_superseded_shared` 3 | xrplnsapi `resolve_user.go:50 ResolveUser` 4 | WayfarerMobile `GroupsService.cs:324 ParseLatestLocationsResponse` 5 | CogniRelay `maintenance/service.py:1691 _validate_segment_history` 8 |
| 5 | Wayfarer `LogsController.cs:174 ReadLastLinesWithPositionAsync` 4 | ripgrep `walk.rs:1190 Walk.next` 5 | CogniRelay `shared_service.py:403 shared_update_service` 6 | same depth-8 outlier |
| 6 | CogniRelay `artifact_lifecycle/service.py:1681 artifact_lifecycle_maintenance_service` 5 | CogniRelay `query_index.py:201 CoordinationQueryIndex.rebuild_shared` 6 | CogniRelay `segment_history/service.py:1163 segment_history_maintenance_service` 7 | same depth-8 outlier |

Depth-5 `CalculateTripBoundingBox`, `artifact_lifecycle_maintenance_service`, and
`ParseLatestLocationsResponse` require several region/type/error contexts and
merit inspection. `Walk.next` is a coherent iterator state machine and an
important “inspect but probably keep” example. Guard clauses or extraction can
help, but the metric must not force them for inherent state machines or
traversals. Candidates 5 and 6 omit useful depth-5 findings.

## 13. Nesting final decision

Use `reviewAt: 4` and enable the guard by default. This agrees in scale with the
two broadly comparable mature depth rules and intervenes only above four active
normalized executable contexts. Five and six are too permissive for the stated
reasoning burden.

## 14. Complexity distributions

These are #26 semantics: one plus normalized decisions, zero short-circuit
contribution, and independent represented anonymous callables.

| Project / language | n | median / P75 / P90 / P95 / P99 / max |
|---|---:|---|
| Wayfarer / C# | 3,980 | 1 / 2 / 4 / 7 / 13 / 33 |
| Wayfarer / JavaScript | 1,348 | 1 / 3 / 5 / 8 / 13 / 20 |
| Wayfarer / TypeScript/Vue | 1,289 | 1 / 2 / 3 / 5 / 8 / 20 |
| CogniRelay / Python | 1,319 | 2 / 5 / 11 / 16 / 32 / 86 |
| CogniRelay / JavaScript | 28 | 2 / 2 / 3 / 4 / — / 5 |
| xrplnsapi / Go | 18 | 2.5 / 4 / 9 / 10 / — / 10 |
| WayfarerMobile / C# | 2,925 | 1 / 2 / 5 / 7 / 11 / 40 |
| ripgrep / Rust | 3,219 | 1 / 1 / 3 / 5 / 12 / 24 |
| nowinandroid / Kotlin | 1,237 | 1 / 1 / 1 / 2 / 3 / 8 |

## 15. Complexity candidates

Precedent spans roughly 10–20 but usually counts more language noise. The
current-facts distribution therefore justified 10, 12, 15, and 20.

| `reviewAt` | REVIEW count | Rate | Assessment |
|---:|---:|---:|---|
| 10 | 316 | 2.06% | catches worthwhile cases but is eager in branch-heavy Python and C# |
| 12 | 215 | 1.40% | defensible, but still catches more coherent normalization/mapping code |
| 15 | 130 | 0.85% | conservative common intervention point with meaningful medium findings |
| 20 | 62 | 0.40% | misses several branching-responsibility cases worth inspecting |

At 10 / 12 / 15 / 20, rates were: Wayfarer C# 1.63 / 1.13 / 0.65 / 0.23%;
Wayfarer JavaScript 2.08 / 1.26 / 0.30 / 0%; Wayfarer TypeScript/Vue 0.54 /
0.16 / 0.08 / 0%; CogniRelay Python 10.01 / 7.73 / 5.31 / 3.49%;
WayfarerMobile C# 1.37 / 0.82 / 0.41 / 0.17%; ripgrep Rust 1.37 / 0.78 /
0.53 / 0.06%; and zero for the other sampled groups.

## 16. Complexity boundary inspection

| Candidate | Below | At/around | Moderately above | Major outlier |
|---:|---|---|---|---|
| 10 | xrplnsapi `xrpl_account.go:35 GetAccountUsers` 9 | xrplnsapi `resolve_user.go:50 ResolveUser` 10 | WayfarerMobile `OsmLiveTileCacheClient.cs:64 FetchAsync` 13 | CogniRelay `service.py:1264 invoke_tool_by_name` 86 |
| 12 | CogniRelay `config.py:360 _validate_segment_history_settings` 11 | CogniRelay `validation.py:71 _upgrade_legacy_structured_entry_timestamps` 12 | Wayfarer `TripsController.cs:1013 UpdateRegion` 15 | same 86 outlier |
| 15 | ripgrep `glob.rs:901 Parser.parse_star` 14 | WayfarerMobile `GroupsService.cs:324 ParseLatestLocationsResponse` 15 | CogniRelay `compare.py:16 _compare_values` 18 | same 86 outlier |
| 20 | ripgrep `fish.rs:13 generate` 16 | Wayfarer `leafletAdapter.ts:386 focusActiveEntity` 20 | ripgrep `hiargs.rs:114 HiArgs::from_low_args` 24 | same 86 outlier |

Values of exactly 15 pass. Additional examples were Wayfarer `UpdateRegion`,
CogniRelay `_assemble_mixed_retrieval_bundle`, and ripgrep
`SearcherTester.configs`. Just above the selected boundary:

- Wayfarer `Areas/Api/Controllers/GroupsController.cs:197`
  `GroupsController.Query` (16) mixes authorization, filtering, and
  privacy branches and is a strong REVIEW.
- CogniRelay `app/config.py:229` `config._load_tokens_file` (17) is coherent configuration
  normalization and may reasonably remain unchanged.
- WayfarerMobile `src/WayfarerMobile.Core/Helpers/SegmentAnchorResolver.cs:44`
  `SegmentAnchorResolver.Resolve` (17) has substantial validation
  responsibility and deserves inspection.
- ripgrep `crates/core/flags/complete/fish.rs:13` `fish.generate` (16) is a coherent match mapping and is a useful
  no-refactor example.

Major strong signals survive zero-short-circuit normalization:
`invoke_tool_by_name` (86), `SendTileRequestCoreAsync` (33),
`PlaceOperationsHandler.UpdatePlaceAsync` (40), and
`HiArgs::from_low_args` (24).

## 17. Complexity final decision

Use `reviewAt: 15` and enable complexity by default when #27 ships. Ten and 12
are valid project choices but too eager as a cross-language default. Twenty
restricts the guard too closely to extremes. Fifteen asks for inspection once a
callable has more than 15 normalized paths without treating coherent branching
as an automatic defect.

## 18. Default-enable decision per guard

All three guards should be enabled by default. Their selected aggregate rates
are low, boundary findings are generally worth looking at, and each addresses a
distinct cost: oversized local units, simultaneous control contexts, and broad
branching responsibility. Zero-config activation makes the advertised guard set
real rather than requiring each project to invent thresholds independently.

## 19. Configuration override/disable model

The future production contract is uniform:

- omitted guard: enabled with its built-in default;
- `{ "enabled": false }`: explicitly disabled, even if `reviewAt` is also present;
- `{ "enabled": true }`: enabled with the built-in default;
- `{ "reviewAt": N }`: enabled with project override `N`;
- `{ "enabled": true, "reviewAt": N }`: enabled with override `N`.

An explicit `reviewAt` must be a positive JSON integer. Boolean, float, string,
zero, and negative values are invalid. Exactly the effective threshold passes;
greater values review. Callable size, nesting, and complexity never fail. No
per-language default table, preset, or profile is introduced.

Projects and users may intentionally override or disable guards. Coding agents
may not raise thresholds, disable guards, or rewrite configuration merely to
silence findings without explicit authorization.

## 20. Migration implications

Callable size and nesting currently interpret omission as disabled and require
`enabled: true` plus `reviewAt`. Changing omission to built-in/default-enabled is
a deliberate behavioral change appropriate to the project's pre-release
`0.1.0.dev0` maturity, but it must ship visibly in a focused production PR.

Explicit configuration remains predictable:

- existing `{ "enabled": false }` remains disabled;
- existing `{ "enabled": true, "reviewAt": N }` preserves `N`;
- a supplied `reviewAt` continues to be strict and becomes sufficient to enable;
- `{ "enabled": true }`, previously invalid, uses the built-in default.

Zero-config runs will parse supported source and expose deterministic syntax or
provider failures because callable size and nesting become active. LOC-only lazy
execution remains available when all syntax guards are explicitly disabled.

## 21. Agent-specific usefulness and noise

The defaults warn an agent before it extends an already large local unit, adds a
fifth simultaneous control context, or adds more branching responsibility above
15 normalized complexity. That can reduce unnecessary local reasoning and
source-loading burden qualitatively; no precise token saving was measured.

Conservative rates matter. Excess output can induce mechanical extraction,
metric gaming, and warning fatigue. The selected boundaries deliberately include
coherent counterexamples so policy remains “inspect, then justify or improve,”
not “refactor until the number disappears.”

## 22. Final recommended zero-config behavior

Once the focused callable/nesting activation issue and #27 ship:

```text
code-guard . --changed-only
    -> file LOC: REVIEW > 400, FAIL > 600
    -> callable size: REVIEW > 80
    -> nesting: REVIEW > 4
    -> cyclomatic complexity: REVIEW > 15
```

Only LOC can FAIL. Explicit user/project configuration can override or disable
each syntax guard under the contract above.

## 23. Remaining risks and qualifications

- This is a small, intentionally heterogeneous corpus, not a statistical claim
  about all software.
- Framework and generated-code conventions can still produce project-specific
  noise; authorized overrides remain necessary.
- Callable boundaries and supported syntax follow the production provider, so
  future coverage changes can shift distributions and should trigger review of
  this calibration rather than silent threshold churn.
- The nowinandroid callable-count delta described above should be retained in
  future reproduction notes.
- Default activation increases ordinary parser exposure. Cross-platform CI and
  deterministic error tests are required in the implementation slices.
- REVIEW must never become an instruction to game, flatten, or mechanically
  split coherent code.
