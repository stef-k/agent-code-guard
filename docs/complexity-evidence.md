# Cyclomatic Complexity Evidence

## Executive conclusion

**Outcome C — useful, but language-specific normalization and callable coverage remain necessary.** Complexity is deterministic when calculated as `1 + DecisionFact count`, and high values dominated by conditions, loops, catches, and executable selection arms usually identify code worth inspecting. The present facts do not yet support a comparable universal scale or production guard, however. Repeated short-circuit fallback/default expressions systematically inflate JavaScript and some C# results, while opaque lambdas in Kotlin, C#, Python, Go, and Java can hide control flow entirely.

Admission decision: **NEEDS MORE EVIDENCE / NO-GO for the production guard in this PR.** A project-configured `reviewAt` would be useful after those two semantics are settled. No universal REVIEW default and no FAIL threshold are justified.

## Methodology

Sampling ran on 2026-08-22. Each repository was shallow-cloned at its default branch into an OS-temporary corpus outside this repository, and its exact HEAD was recorded before analysis. Repositories were input-only. The research driver calls runner-owned `resolve_scope` with explicit production roots, filters only documented exclusions, calls production `analyze_files`, and groups the resulting `DecisionFact` values by range-qualified `CallableKey`. It never parses, walks syntax, reads source to rediscover decisions, or imports Tree-sitter nodes.

Baseline complexity is one plus all current normalized decisions. Percentiles use deterministic nearest-rank selection. Exploratory `>5`, `>10`, `>15`, and `>20` counts are distribution aids, not proposed thresholds. The only alternatives tested were removal of `short_circuit_boolean`, removal of Python `comprehension`, and removal of Rust `switch_arm`, each motivated by inspected real examples.

Production/application roots drove the distributions. Tests, generated migrations, build outputs, vendored dependencies, and embedded third-party source were excluded. Manual inspection used deterministic low, median, P75/P90, and highest-score strata. Approximately 25 callables per major language were reviewed (all 17 Go callables; 30 Kotlin callables because its distribution was compressed), with ten highest-score callables where the sample permitted.

## Corpus and source selection

| Repository | Default branch | Pinned commit | Languages sampled | Production roots and exclusions |
|---|---|---|---|---|
| `stef-k/Wayfarer` | `main` | `d4ae7142cfabb50e33fb8d28bf8266b170009f37` | C#, JavaScript, TypeScript, Vue scripts | repository production roots; excluded `tests`, generated `Migrations`, `tools`, coverage, `wwwroot/lib`, minified JS, build output |
| `stef-k/CogniRelay` | `main` | `945d179366b9b6fa6a2ba4e4d386c349bbdbe210` | Python, JavaScript | `app`, `cognirelay`, `setup.py`; excluded tests, tools, agent assets |
| `stef-k/xrplnsapi` | `master` | `ed1175be0415bb193db41ca174387a9cacb41652` | Go | complete repository production source; no supported test files present |
| `stef-k/WayfarerMobile` | `main` | `0162d373026eb5caea337f8c8f76c31328d167e7` | C# | `src`; excluded embedded third-party Quill and two parser-rejected files |
| `BurntSushi/ripgrep` | `master` | `3fce3b5bb0236da2df6d99672afb8a719642eca7` | Rust | `crates`, root `build.rs`; excluded test/bench roots and fuzz source |
| `android/nowinandroid` | `main` | `7d45eae4f8720a0c77f507712ba2437ff974b6ed` | Kotlin | `app`, `app-nia-catalog`, `core`, `feature`, `sync`; excluded tests, benchmarks, generated fixtures, parser-rejected `core/designsystem` and screenshot tooling |

Three individual C# files were inapplicable because the pinned C# grammar reported syntax errors: Wayfarer's `Parsers/WayfarerKmlParser.cs`, and WayfarerMobile's `MauiProgram.cs` and `Handlers/CustomWebViewHandler.cs`. Modern Compose syntax caused deterministic parse errors in nowinandroid's design-system and screenshot-tooling roots. These are recorded analyzer limitations, not silent omissions. No analyzed file produced a parse failure.

The evidence run also found and fixed a blocking production adapter defect: repeated access to native Tree-sitter point properties could return inconsistent coordinates and segfault on real C# input. The fix snapshots each point once before original-source mapping and has a focused regression test. It changes neither fact categories nor guard behavior.

## Counts and distributions

The final corpus contains **1,132 supported files and 11,870 measured callables**.

| Project / language | Files (project) | Callables | Min | Median | P75 | P90 | P95 | Max | Mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Wayfarer / C# | 460 | 1,887 | 1 | 2 | 5 | 8 | 12 | 43 | 3.66 |
| Wayfarer / JavaScript | 460 | 1,348 | 1 | 2 | 4 | 7 | 9 | 28 | 2.95 |
| Wayfarer / TypeScript and Vue scripts | 460 | 1,289 | 1 | 1 | 2 | 4 | 6 | 22 | 2.17 |
| CogniRelay / Python | 85 | 1,173 | 1 | 3 | 7 | 14 | 22 | 87 | 6.14 |
| CogniRelay / JavaScript | 85 | 28 | 1 | 2 | 3 | 13 | 16 | 28 | 4.25 |
| xrplnsapi / Go | 13 | 17 | 1 | 3 | 4 | 11 | 11 | 11 | 3.47 |
| WayfarerMobile / C# | 299 | 2,433 | 1 | 1 | 3 | 6 | 9 | 51 | 2.70 |
| ripgrep / Rust | 90 | 3,219 | 1 | 1 | 1 | 3 | 6 | 30 | 1.78 |
| nowinandroid / Kotlin | 185 | 476 | 1 | 1 | 1 | 1 | 2 | 7 | 1.12 |

| Project / language | Above 5 | Above 10 | Above 15 | Above 20 |
|---|---:|---:|---:|---:|
| Wayfarer / C# | 361 (19.13%) | 118 (6.25%) | 54 (2.86%) | 25 (1.32%) |
| Wayfarer / JavaScript | 188 (13.95%) | 50 (3.71%) | 23 (1.71%) | 7 (0.52%) |
| Wayfarer / TypeScript | 83 (6.44%) | 18 (1.40%) | 7 (0.54%) | 2 (0.16%) |
| CogniRelay / Python | 366 (31.20%) | 178 (15.17%) | 102 (8.70%) | 69 (5.88%) |
| CogniRelay / JavaScript | 5 (17.86%) | 3 (10.71%) | 2 (7.14%) | 1 (3.57%) |
| xrplnsapi / Go | 3 (17.65%) | 2 (11.76%) | 0 | 0 |
| WayfarerMobile / C# | 301 (12.37%) | 69 (2.84%) | 20 (0.82%) | 10 (0.41%) |
| ripgrep / Rust | 170 (5.28%) | 55 (1.71%) | 22 (0.68%) | 5 (0.16%) |
| nowinandroid / Kotlin | 1 (0.21%) | 0 | 0 | 0 |

The sharp project differences make the exploratory levels unsuitable as product defaults. Python's P90 is 14 while Kotlin's is 1, and those values partly reflect callable coverage rather than engineering burden.

## Decision-category observations

| Project / language | Category totals |
|---|---|
| Wayfarer / C# | condition 2,609; short-circuit 1,153; ternary 401; catch 392; loop 363; switch arm 99 |
| Wayfarer / JavaScript | condition 1,331; short-circuit 802; ternary 357; catch 102; loop 22; switch arm 17 |
| Wayfarer / TypeScript | condition 664; short-circuit 524; ternary 264; catch 27; loop 20; switch arm 3 |
| CogniRelay / Python | condition 3,018; short-circuit 1,282; catch 627; loop 477; ternary 345; comprehension 284 |
| xrplnsapi / Go | condition 32; loop 5; short-circuit 5 |
| WayfarerMobile / C# | condition 2,154; short-circuit 678; catch 620; switch arm 311; ternary 196; loop 179 |
| ripgrep / Rust | condition 1,010; switch arm 990; loop 257; short-circuit 234; pattern guard 25 |
| nowinandroid / Kotlin | switch arm 25; condition 23; catch 7; short-circuit 3 |

Conditions, loops, and catches correlate well with review burden. Executable switch/when/match arms are useful when they represent distinct behavior; grouped/default arms remain correctly excluded. Ternaries are useful in aggregate but do not by themselves imply a refactor. Short-circuit operators are the principal systematic noise source. Pattern guards add real choice and should remain decisions.

## Contentious constructs

- **Python comprehensions and generators:** counting each comprehension/generator node once is useful. Nested comprehensions naturally contribute once per nested iteration. Filters are already expressed through their condition facts and must not receive another invented weight. Removing comprehensions did not change Python median/P75/P90/P95/max (3/7/14/22/87) and reduced `>10` from 178 to 168, so they are not the source of the high Python tail.
- **Boolean `and` / `or`, `&&` / `||`:** they represent real path choices, but counting every operator is not review-stable. CogniRelay `applyDetail` scores 28 almost entirely because 24 `value || fallback` expressions are independent presentation defaults. Removing short circuits changed its JavaScript P90/P95/max from 13/16/28 to 3/4/5. Wayfarer C# P95/max changed 12/43 to 9/33; Python P90/P95 changed 14/22 to 12/18. A future pass should test one contribution per maximal boolean decision expression, not zero versus every operator.
- **Fallback/null-aware operators:** JavaScript/TypeScript `??`, optional chaining, C# `??`/`?.`, and Kotlin Elvis/safe navigation remain non-decisions. Real examples supported that policy: these idioms mostly supply values or safely propagate absence and would add noise similar to JavaScript fallback `||`.
- **Conditional/ternary expressions:** retain one decision. Dense runs can signal expression-heavy branching, but isolated uses are normal.
- **Switch, `when`, and `match`:** retain one per executable non-default arm plus explicit pattern guards. Removing Rust arms lowered P90/P95 from 3/6 to 2/4 and `>10` from 55 to 20, but it made inspected parsers and state machines materially less visible. Pattern-oriented control is comparable when grouped arms are normalized by executable destination.
- **Go error checks:** repeated early-return checks raise values, but inspected high values remained review-useful because they accumulated with loops and response assembly. The small Go corpus prevents threshold inference.
- **Kotlin/Compose:** Elvis and safe navigation correctly add nothing, but Compose bodies concentrate behavior inside lambdas that the current contract intentionally treats as opaque. This is a coverage problem, not evidence that Compose has trivial complexity.
- **C# pattern-heavy switch expressions:** a keyword-to-icon mapping scored 51 through 18 arms and 31 boolean operators. The mapping is readable and coherent; the score is a useful inspection anchor but a poor automatic refactor command.
- **Rust Result/Option idioms:** `if let`, `while let`, match arms, guards, and closures already represented as callables behave deterministically. Match-heavy parser/state code was generally worth inspection, though not necessarily simplification.

## Callable and callback boundary

Named functions/methods, assigned JS/TS functions/arrows, anonymous callbacks with deterministic identities, represented Rust closures, and nested/local callables should be reported independently. Production ownership already prevents child decisions from being counted in the parent, and the evidence showed useful high callback findings in real frontend code without widespread noise.

The boundary is nevertheless incomplete across languages. Kotlin, C#, Python, Go, and Java lambdas/local anonymous functions remain opaque, so their decisions disappear rather than belonging to either child or owner. `nowinandroid`'s `NiaCatalog` spans lines 58–373 and measures 1 because its Compose content is lambda-owned. A future complexity guard must either represent mainstream lambdas consistently or explicitly restrict supported complexity coverage; silently comparing the current Kotlin distribution with Rust/JS is not acceptable.

## Signal and noise examples

Strong signals (repository paths refer to the pinned commits above):

- CogniRelay `app/discovery/service.py:1264`, `invoke_tool_by_name`, 87: 85 conditions expose a very large dispatch/validation responsibility.
- Wayfarer `Services/TileCacheService.cs:1000`, `RetrieveTileAsync`, 38: conditions, five catches, boolean choices, and ternaries reflect genuinely difficult retry/cache/fallback flow.
- ripgrep `crates/core/flags/hiargs.rs:114`, `HiArgs::from_low_args`, 30: match arms, guards, conditions, and option-dependent normalization form a meaningful review anchor.
- xrplnsapi `controllers/resolve_user.go:50`, `ResolveUser`, 11: nested conditional assembly and loops are visibly more involved than the corpus median.
- Wayfarer TypeScript `leafletAdapter.ts:386`, `focusActiveEntity`, 22: 13 conditions and six ternaries correspond to state-sensitive UI behavior worth inspection.

Noisy or misleading examples:

- CogniRelay `app/ui/static/ui_live.js:90`, `applyDetail`, 28: 24 fallback `||` expressions dominate otherwise linear DOM field population.
- WayfarerMobile `ActivitySyncService.cs:371`, `SuggestIconForActivity`, 51: a coherent declarative mapping is inflated by boolean keyword alternatives; inspect, do not mechanically split.
- WayfarerMobile `TimelineImportService.cs:572`, `HasMoreData`, 26: 25 short-circuit checks make a compact predicate appear equivalent to a large state machine.
- nowinandroid `Catalog.kt:58`, `NiaCatalog`, 1: opaque Compose lambdas create a severe false negative.
- Low scores can also hide data-flow, concurrency, or semantic coupling; this metric only anchors syntactic decision review.

## Cross-language and threshold conclusions

1. Deterministic measurement is useful: **yes**.
2. One common normalized scale is defensible today: **no**; condition/loop/catch/arm semantics are comparable, but boolean weighting and opaque callable coverage are not.
3. One universal REVIEW default is defensible: **no**.
4. Project-configured `reviewAt` would be useful: **yes, after the two normalization blockers are resolved**.
5. Language-specific qualification is required today: **yes**, but a permanent per-language threshold table would encode corpus accidents.
6. Language-specific default thresholds are maintainable: **no**; avoid an arbitrary table.

The next evidence slice should test exactly one short-circuit contribution per maximal boolean expression and extend/reset callable ownership for mainstream lambdas in the currently opaque languages. If that produces comparable distributions, the smallest future configuration remains:

```json
{
  "guards": {
    "cyclomaticComplexity": {
      "enabled": true,
      "reviewAt": 12
    }
  }
}
```

`12` is illustrative only. Configuration should require an explicit positive JSON integer, be opt-in when omitted/false, use no per-language defaults, overrides, exemptions, or FAIL threshold, and forbid agents from raising/disabling it without authorization.

## Explainability and result recommendation

A future PASS/REVIEW callable finding should contain `path`, range-qualified callable identity, original source range, embedded language, measured complexity, configured threshold, state, boundary kind, and all **non-zero** normalized category counts. Non-zero counts are compact and more actionable than top contributors alone. An optional deterministic highest-contributing decision line is cheap only if it is calculated from existing fact locations; do not expose AST nodes or dumps.

```json
{
  "guard": "cyclomaticComplexity",
  "path": "src/example.cs",
  "callable": "Example.Run",
  "range": { "startLine": 10, "endLine": 42 },
  "embeddedLanguage": "csharp",
  "boundaryKind": "callable",
  "state": "REVIEW",
  "details": {
    "complexity": 14,
    "reviewAt": 12,
    "decisions": { "condition": 6, "loop": 2, "switch_arm": 5 }
  }
}
```

Use the actual snake-case production categories. JSON should include every measured callable; human output should include REVIEW findings only. REVIEW must route the stable complexity policy ID.

## Policy recommendation

Complexity is an inspection anchor, not an automatic refactor instruction or score target. Do not split coherent code mechanically, replace readable branching with clever expressions, or hide decisions behind meaningless helpers. Interpret mappings, validation predicates, language idioms, generated structure, and callback-heavy code in context. Agents may honor explicit project configuration but may not disable the guard or raise thresholds merely to silence findings without explicit authorization. No FAIL behavior is supported by this evidence.

## Shared-facts, performance, and admission assessment

Measurement consumes the one existing `AnalysisFacts` value after runner scope resolution. Grouping decisions by immutable `CallableKey` is linear in callables plus decisions and requires no additional parse, source read, service, database, or toolchain.

| Admission criterion | Assessment |
|---|---|
| Deterministic anchor | PASS after the native-point defect fix |
| Engineering value | PASS |
| Broad applicability | QUALIFIED by opaque callable families |
| Distinct responsibility | PASS; agent-facing review anchoring is distinct from project linting |
| Stable measurement semantics | QUALIFIED by boolean weighting and callable coverage |
| Explainability/actionability | PASS with category breakdown and callable range |
| Useful state model | PASS for PASS/REVIEW only |
| Signal-to-noise | QUALIFIED; strong branching signal, demonstrated boolean noise and lambda blind spots |
| Threshold/config evidence | CONFIGURABLE ONLY; no default evidence |
| Gaming risk | MITIGATED by policy, never eliminated |
| Scope compatibility | PASS; consumes `ResolvedScope.files` |
| Architecture fit/cost | PASS; shared facts, no reparse |
| Deterministic failure behavior | QUALIFIED by explicit grammar rejections |
| Portability/testability | QUALIFIED; normal pipeline is portable, real grammar coverage needs follow-up |

## Final decision and future vertical scope

**Final outcome: Outcome C.**

**Current production recommendation: NO-GO / NEEDS MORE EVIDENCE.** Do not open the vertical production implementation issue yet. First settle maximal-expression short-circuit normalization and mainstream lambda ownership/coverage with focused analyzer fixtures plus a targeted rerun of the pinned evidence corpus. If those qualifications close, the future vertical issue should deliver one opt-in configurable-only slice: fact-only calculation, strict `enabled`/`reviewAt` config, one shared runner analysis, PASS/REVIEW findings with non-zero decision breakdown, human/JSON reporting, lazy complexity policy routing, deterministic errors, fixtures, and Ubuntu/Windows/macOS CI. It must not add FAIL, universal or per-language defaults, scope discovery, or alternate parsing.

## #25 Boolean normalization and lambda ownership follow-up

### Settled syntax semantics

Issue #25 retained every #14 category except short-circuit weighting. Three deterministic candidates were compared: every operator (#14 baseline), one fact per maximal connected short-circuit expression, and zero short-circuit facts. The maximal candidate treats `&&`, `||`, Python `and`/`or`, and transparent parentheses as one connected tree, with other expression constructs as boundaries. It fixes chain-length inflation but leaves separate fallback expressions overweighted.

The selected production rule is therefore **zero short-circuit contribution**. `a && b && c`, mixed/grouped expressions, predicates, assignments, returns, call arguments, ternary-contained booleans, and `value || default` emit no `DecisionFact`. Conditions, loops, catches, ternaries, executable arms, guards, and comprehensions still represent the surrounding control structure. The pinned zero-candidate comparison below contradicts the earlier concern that boolean facts were needed to preserve strong review signal. Nullish coalescing, optional/safe navigation, and Kotlin Elvis remain excluded as before.

Kotlin lambdas/anonymous functions, C# lambdas/anonymous delegates, Go function literals, Java lambdas, and Python expression lambdas now emit provider-neutral `CallableFact` values. Anonymous identities reuse `<callback@original-line:original-byte-column>` beneath their lexical owner. The range is the callable syntax, not its assignment or call site; `boundaryKind` is `callback`. Each receives a unique range-qualified `CallableKey`. Parent traversal stops at child callables, so decisions do not double count and nesting resets. Python lambdas can contribute conditional expressions, but not statement controls or boolean facts.

### Pinned-corpus comparison

The exact six #14 SHAs and recorded production-root exclusions were reused. “Maximal” is the first #25 candidate with lambda coverage and ends with its `>10` count. “Zero final” removes normalized boolean facts and ends with `>5/>10/>15/>20` counts.

| Project / language | Maximal candidate | Zero final |
|---|---|---|
| Wayfarer / C# | 3,980; 1/2/5/8/36; 95 | 3,980; 1/2/4/7/33; 283/65/26/9 |
| Wayfarer / JavaScript | 1,348; 2/3/7/9/25; 44 | 1,348; 1/3/5/8/20; 111/28/4/0 |
| Wayfarer / TypeScript/Vue | 1,289; 1/2/4/6/22; 15 | 1,289; 1/2/3/5/20; 39/7/1/0 |
| CogniRelay / Python | 1,319; 2/6/13/20/87; 173 | 1,319; 2/5/11/16/86; 298/132/70/46 |
| CogniRelay / JavaScript | 28; 2/3/13/16/28; 3 | 28; 2/2/3/4/5; 0/0/0/0 |
| xrplnsapi / Go | 18; 2.5/4/11/11/11; 2 | 18; 2.5/4/9/10/10; 2/0/0/0 |
| WayfarerMobile / C# | 2,925; 1/3/6/8/41; 59 | 2,925; 1/2/5/7/40; 242/40/12/5 |
| ripgrep / Rust | 3,219; 1/1/3/6/30; 53 | 3,219; 1/1/3/5/24; 150/44/17/2 |
| nowinandroid / Kotlin | 1,197; 1/1/1/2/8; 0 | 1,197; 1/1/1/2/8; 3/0/0/0 |

The zero candidate removes all normalized boolean totals. The noisy anchors improve materially: `applyDetail` 28→4, `HasMoreData` 2→1, and `SuggestIconForActivity` 36→20. Strong review signals survive without boolean facts: `invoke_tool_by_name` 87→86, `RetrieveTileAsync` 36→32, `HiArgs::from_low_args` 30→24, and `focusActiveEntity` 22→20. Their remaining conditions, catches, arms, guards, and ternaries explain why they still deserve inspection. Zero is simpler, uniformly structural, and materially quieter than the maximal candidate.

`NiaCatalog` itself remains 1 because it delegates to lambdas, but its file now exposes 100+ nested callable boundaries and the conditions/`when` arms owned by them. Compose calls and UI hierarchy add no controls. This is correct generic ownership, not a framework rule. Focused Kotlin, C#, Go, Java, and qualified Python fixtures prove deterministic identity/range, parent exclusion, and nested reset. Existing JS/TS/JSX/Vue and Rust/C++/PHP/Swift/Dart closure tests remain green.

Callable size and nesting intentionally gain these callables: size uses each callable-syntax range, nesting uses only its `CallableKey`, and existing parents remain unpolluted. Existing non-lambda facts and LOC are unchanged. No complexity guard, configuration, result, policy routing, default, or FAIL state was added.

### Admission reassessment

| Criterion | Result |
|---|---|
| Deterministic anchor | PASS; syntax facts and coordinate ownership are deterministic |
| Engineering value | PASS; strong branching anchors survive |
| Broad applicability | PASS with Python expression qualification |
| Distinct responsibility | PASS |
| Stable measurement semantics | PASS; short-circuit syntax uniformly contributes zero |
| Explainability/actionability | PASS; non-zero category counts identify the remaining branching source |
| State semantics | PASS; only prospective PASS/REVIEW was defensible |
| Signal/noise | PASS; noisy anchors collapse while mandatory strong signals remain high |
| Threshold/config evidence | PASS for configurable-only; no universal or language default is justified |
| Gaming resistance | PASS with policy; boolean rewrites cannot change the score |
| Scope compatibility | PASS |
| Architecture fit/cost | PASS; existing facts suffice |
| Deterministic failure behavior | PASS; syntax errors and lazy LOC behavior are preserved |
| Portability/testability | PASS; adapters are fixture-tested across supported platforms |

**Final decision: ACCEPT — CONFIGURABLE ONLY.** The zero-short-circuit rule and mainstream lambda ownership close #14's concrete normalization and coverage blockers. A separate production issue should deliver one opt-in vertical slice requiring a project-supplied positive `reviewAt`; exactly the threshold passes, larger values review, and complexity never fails. There is no universal or per-language default, and agents may not weaken project configuration merely to silence findings.
