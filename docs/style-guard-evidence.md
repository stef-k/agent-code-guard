# CSS/SCSS maintainability guard evidence

## Executive conclusion

Issue #38 evaluated four candidates independently under D27 over 235 manually maintained CSS/SCSS documents and 4,117 authored blocks from five pinned projects.

- **Rule/block physical size: ACCEPT — CONFIGURABLE ONLY.** A source-ranged local block span is distinct from file LOC (document LOC versus maximum block span Pearson correlation `0.3471`) and the largest style-rule, mixin, and responsive-region facts identify plausible component/responsibility review anchors. The evidence does not support one universal boundary: at `> 80`, corpus finding rates range from `0.12%` to `3.21%` and affected-document rates from `6.67%` to `29.79%`; container kinds have materially different meanings. Any later production guard must require a positive project-supplied REVIEW threshold, remain disabled when omitted, and report the block kind. It must never FAIL or recommend metric-only splitting/compression.
- **SCSS selector nesting depth: REJECT / OUT OF SCOPE.** It is deterministic when selector, at-rule, and Sass control ancestry are kept separate, but Stylelint's `max-nesting-depth` already owns this exact concern with mature at-rule and pseudo-class exceptions. `&` may express a pseudo-state, BEM suffix, reversed context, interpolation, or selector-function input rather than one uniform coupling cost. Code Guard adds no distinct agent-maintainability responsibility.
- **Selector complexity/specificity: REJECT / OUT OF SCOPE.** Stylelint directly owns maximum specificity, compound selectors, combinators, IDs, qualifying types, and related selector policy. Reimplementing its CSS Nesting and interpolation semantics would be a worse specialist linter, not a Code Guard signal.
- **Declaration count/rule fan-out: REJECT / OUT OF SCOPE.** It is mostly a formatting-independent correlate of block size. Its strongest outliers are legitimate theme/token blocks: four of the five blocks above 20 declarations are custom-property-dominated (`49/50`, `30/31`, `30/31` and a theme-token block). It contributes no better ownership boundary.

No production CSS/SCSS guard, configuration, applicability, dependency, or executable `AnalysisFacts` behavior is added. The accepted measurement needs a separate future production issue; this evidence PR does not invent one.

## Candidate definitions and measurement semantics

All candidate comparisons use strict greater-than boundaries; equality passes. Facts retain kind, normalized header, one-based inclusive start/end lines, and deterministic authored order.

1. **Block physical size** is the inclusive physical source span from a block's header through its closing brace. Blank lines, comments, declarations, and nested blocks count. LF and CRLF have identical line values. The final unterminated record counts. Facts distinguish style rules, conditional/container at-rules, keyframes and keyframe steps, mixins, functions, and Sass controls. Nested content counts toward its parent because the parent owns that source region; findings may therefore overlap and must identify their kind.
2. **SCSS selector depth** counts authored style-rule ancestors including the current rule. At-rule ancestry and Sass control ancestry are recorded separately and do not inflate selector depth. Root selectors are depth 1. `@media`, `@supports`, `@container`, `@layer`, and other block at-rules have a separate depth. `@if`, `@else`, `@for`, `@each`, and `@while` have a separate control depth. Mixins/functions are separate owner kinds. Keyframe steps are not selectors.
3. **Selector complexity** records, per selector list, list length and the maximum component, combinator, and research specificity values among its selectors. Commas inside brackets/parentheses do not split selectors. Interpolation remains opaque. These values only quantify overlap; they are not proposed production semantics.
4. **Declaration count** counts direct declarations in a block, including a final declaration without a semicolon, but excludes nested-block declarations. Custom-property declarations are separately counted so token/theme domination can be inspected.

Braces in block comments, SCSS line comments, quoted strings, escapes, and `#{...}` interpolation never open or close structural blocks. Empty blocks have zero declarations and a one-line span when authored on one line. Unicode is decoded as UTF-8 and does not alter coordinates.

Physical lines are retained rather than nonblank lines: excluding blank/comment lines adds a formatting-policy question without changing block ownership. This is still gameable through line compression, so an eventual policy must forbid formatting solely to lower the metric and must let a coherent large block remain unchanged after review.

## Parser/provider evaluation and failure behavior

The evidence authority is the repository's standard-library-only bounded scanner in `research/style_guard_sample.py`. It is not a general CSS validator. Its single pass recognizes structure needed by the admitted measurement, preserves exact authored line ranges, has deterministic source order, and has no network, process, native binary, platform, or new license cost. The repository is MIT licensed; the scanner ships under that license and ran under the same Python runtime used by Windows/Ubuntu/macOS CI.

Malformed or partially edited input is handled explicitly. An unmatched closing brace increments `errorCount` and yields no invented block. Each still-open block is bounded at EOF, marked `recovered: true`, and increments recovery telemetry. An unterminated comment, string, or interpolation also increments the error count. Recovered facts remain measurable because the only admitted candidate is a physical source range; recovery is reported and never becomes a CSS-syntax finding. Unsupported format, non-UTF-8 input, or an inability to produce bounded facts is a structured measurement error, never a silent skip. All 235 selected corpus documents measured with zero recoveries; compact tests lock malformed recovery separately.

The already-pinned `tree-sitter==0.26.0` plus MIT `tree-sitter-language-pack==1.14.3` were evaluated. Their CSS/SCSS trees provide byte/point ranges and cross-platform wheels, and Tree-sitter exposes explicit `ERROR` and zero-width `MISSING` recovery nodes. However, the SCSS grammar produced an `ERROR` for an ordinary interpolated declaration value in the evaluation fixture and then mis-owned following structure. Shipping a future physical-span guard through it would also retain the existing native grammar bundle when the admitted fact needs only balanced source structure. Tree-sitter remains a possible future provider only if fixtures prove its selected SCSS version authoritative; it is not justified here.

PostCSS/SCSS and Dart Sass would add JavaScript or Sass runtime/toolchain ownership. Dart Sass is compilation authority but does not preserve the simple authored-block fact contract without additional mapping. A regex-only counter cannot handle nested comments/strings/interpolation. The bounded scanner is therefore the smallest deterministic evidence provider. It is research tooling, not production architecture, and CSS/SCSS facts never enter executable `AnalysisFacts`.

## Pinned corpus and exclusions

Disposable shallow clones were created outside Agent Code Guard. The manifest explicitly selected manually maintained source and excluded minified CSS, vendored CSS/SCSS, compiled output, distribution bundles, `node_modules`, and irrelevant stylelint/Sass test fixtures. Raw clones, manifests, and result dumps are not committed.

| Corpus | Pinned SHA | Documents | Role and retained noise controls |
| --- | --- | ---: | --- |
| `django/django` admin CSS | `6177d5f8497f2c08f9874f5221fd17ce5acd2ad7` | 13 | Conventional application CSS; admin `css/**`, excluding `vendor/**` and minified files. Retains large responsive regions and root theme variables. |
| `primer/css` | `03988c5a5ba248c3b9b11ea96fd4fda5e98849aa` | 111 | Mature component/design system; manually maintained `src/**/*.scss`. Retains intentionally deep `PageLayout` and large component blocks. |
| `twbs/bootstrap` | `1039a4788d6abc368d5485ae6bac84a8f0e3096f` | 49 | Substantial SCSS codebase; `scss/**/*.scss`, excluding `scss/tests/**` and vendored RFS. Retains complex mixins and form components. |
| `picocss/pico` | `0875df4f25373511874f5bfcd117a1bc2006762f` | 47 | Modern CSS-heavy source authored as SCSS; `scss/**/*.scss`, excluding distribution output. Retains module gates, themes, tooltips, and modern selectors. |
| `stef-k/Wayfarer` | `264e74d9e5b9f93c83ce1eff659b399b2eb22cf6` | 15 | Relevant application CSS under Trip Editor, `wwwroot/css`, views, and docs; excludes libraries, bundles, and minified output. Retains the coherent 173-line mobile drawer media region. |

The selected set contains 235 documents, 4,117 blocks, 3,332 style rules/selectors, and 1,807 SCSS style rules. It is heterogeneous but not a statistical population model. Candidate boundaries are engineering probes, not percentile-derived thresholds.

## Distributions

| Candidate | Nodes | Median | P75 | P90 | P95 | P99 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Block physical lines | 4,117 | 5 | 8 | 16 | 28 | 89 | 472 |
| SCSS selector depth | 1,807 | 1 | 2 | 3 | 3 | 4 | 6 |
| Selector components | 3,332 | 1 | 2 | 3 | 4 | 7 | 16 |
| Selector combinators | 3,332 | 0 | 1 | 2 | 2 | 4 | 11 |
| Research specificity scalar | 3,332 | 10 | 20 | 41 | 110 | 130 | 340 |
| Direct declarations/block | 4,117 | 1 | 2 | 5 | 7 | 13 | 50 |

SCSS depth excludes the 28 CSS/SCSS keyframe owners and 55 keyframe steps, 181 at-rules, 404 Sass controls, 103 mixins, and 14 functions from selector ancestry. These distinct counts are why the candidate cannot be called executable nesting.

## Actual finding volume

Each cell is `findings / affected documents / documents with multiple findings`. Node percentages and affected-document percentages follow each table at the most informative comparison boundary.

### All block kinds by physical span

| Corpus | > 40 | > 60 | > 80 | > 120 |
| --- | ---: | ---: | ---: | ---: |
| Django admin | 7/4/2 | 3/2/1 | 3/2/1 | 2/1/1 |
| Primer CSS | 57/29/15 | 20/17/2 | 13/11/1 | 7/6/1 |
| Bootstrap SCSS | 14/9/3 | 8/7/1 | 7/6/1 | 1/1/0 |
| Pico | 59/29/16 | 32/16/10 | 23/14/8 | 13/11/2 |
| Wayfarer | 4/4/0 | 3/3/0 | 1/1/0 | 1/1/0 |
| **All** | **141/75/36** | **66/45/14** | **47/34/11** | **24/20/4** |

At `> 80`, 47 findings are `1.14%` of blocks and affect 34/235 documents (`14.47%`), with 11 multi-finding documents. Per corpus the finding/affected-document rates are Django `0.39%/15.38%`, Primer `0.93%/9.91%`, Bootstrap `1.69%/12.24%`, Pico `3.21%/29.79%`, and Wayfarer `0.12%/6.67%`. This spread and the different meaning of style-rule, at-rule, control, and mixin spans defeat a universal default.

For style rules alone, `> 40/60/80/120` yields `69/32/21/7` findings. At `> 80`, every affected rule is in a different document: a low-noise opt-in responsibility prompt. The remaining all-kind `> 80` findings are 5 at-rules, 15 control containers, and 6 mixins; large keyframes/functions produce none. A future implementation issue must decide configured kind applicability explicitly rather than silently combining unlike owners.

### SCSS selector depth

| Corpus | > 2 | > 3 | > 4 | > 5 |
| --- | ---: | ---: | ---: | ---: |
| Primer CSS | 181/27/24 | 44/14/7 | 5/2/1 | 0/0/0 |
| Bootstrap SCSS | 27/7/5 | 0/0/0 | 0/0/0 | 0/0/0 |
| Pico | 126/17/15 | 38/9/7 | 6/4/1 | 1/1/0 |
| **All SCSS** | **334/51/44** | **82/23/14** | **11/6/2** | **1/1/0** |

At `> 4`, 11 findings are `0.61%` of SCSS rules and affect 6/207 SCSS documents (`2.90%`), with two multi-finding documents. Primer is `0.44%/1.80%`, Bootstrap `0%/0%`, and Pico `1.28%/8.51%`. The low volume does not create distinct ownership: Stylelint already reports this structure with richer exceptions.

### Selector components

| Corpus | > 4 | > 6 | > 8 | > 12 |
| --- | ---: | ---: | ---: | ---: |
| Django admin | 30/9/6 | 5/3/2 | 0/0/0 | 0/0/0 |
| Primer CSS | 7/3/2 | 0/0/0 | 0/0/0 | 0/0/0 |
| Bootstrap SCSS | 5/4/1 | 3/2/1 | 0/0/0 | 0/0/0 |
| Pico | 60/18/10 | 41/14/9 | 20/10/4 | 7/5/1 |
| Wayfarer | 23/4/2 | 0/0/0 | 0/0/0 | 0/0/0 |
| **All** | **125/38/21** | **49/19/12** | **20/10/4** | **7/5/1** |

At `> 8`, all 20 findings (`0.60%`) and all 10 affected documents (`4.26%`) are Pico; four documents have multiple findings. The per-corpus result is `0%` everywhere else. This is project selector methodology, not a universal agent guard. Specificity has even stronger stack effects: Django and Wayfarer P95 are `110` and `111`, while Primer/Bootstrap/Pico are `20/40/65`.

### Direct declarations

| Corpus | > 10 | > 15 | > 20 | > 40 |
| --- | ---: | ---: | ---: | ---: |
| Django admin | 9/4/3 | 3/2/1 | 3/2/1 | 1/1/0 |
| Primer CSS | 18/14/3 | 2/2/0 | 0/0/0 | 0/0/0 |
| Bootstrap SCSS | 8/7/1 | 1/1/0 | 0/0/0 | 0/0/0 |
| Pico | 18/12/4 | 6/6/0 | 2/2/0 | 0/0/0 |
| Wayfarer | 29/11/6 | 6/3/1 | 0/0/0 | 0/0/0 |
| **All** | **82/48/17** | **18/14/2** | **5/4/1** | **1/1/0** |

At `> 15`, 18 findings are `0.44%` of blocks and affect 14 documents (`5.96%`), with two multi-finding documents. Rates vary from Bootstrap `0.24%/2.04%` to Wayfarer `0.74%/20.00%`. Above 20, three Django findings are root/light/dark variable tables and two Pico findings are the coherent light/dark theme mixins. The count is formatting-independent but less informative than the source-ranged owner.

## Boundary inspection and coherent keeps

### Block physical size

- Below (`40–60`): ordinary Primer component wrappers and Bootstrap mixins frequently contain one coherent selector family. A review threshold this low affects almost one-third of documents and is routine noise.
- Near (`60–90`): Primer color-mode mixins (57/89 lines), Bootstrap grid generation (65), Pico tooltip hover media (79), and Wayfarer mobile map/surface regions (64/71) are navigable owner boundaries. Some warrant inspection, but extraction is not automatically an improvement.
- Above: Primer `.form-group` (280), `.PageLayout` (254), Pico tooltip rule (206), Bootstrap validation mixin (145), and Wayfarer's mobile drawer media region (173) are genuine local surfaces. `.PageLayout` mixes responsive pane/content variants and is a plausible review target; the mobile drawer media region is a coherent viewport override whose extraction would separate the responsive behavior from its component.
- Outlier/coherent keep: Django's 472- and 376-line responsive media regions intentionally collect breakpoint overrides; Pico's 468-line module `@if` owns an entire optional forms module; Pico's 254/214-line light/dark mixins are theme tables. Their size is real, but kind-aware review may conclude `coherent; keep`.

The low LOC correlation shows local span is not just file LOC. Overlap still matters: a large control/at-rule can contain large rules, so all ancestor findings should not be emitted blindly. This evidence accepts the anchor, not a finalized finding de-duplication contract.

### SCSS selector depth and `&`

- Below/near: Bootstrap's maximum depth is 3. Repeated `&:hover`, `&:focus`, `&::before`, and BEM suffixes preserve local state/modifier ownership; flattening them would repeat the base selector.
- Above: Primer `PageLayout` supplies four depth-6 rules and Pico navigation supplies one. The Primer chain combines layout variants, breakpoint ownership, pane/content roles, and `&:not(...)`; it is worth reading but Stylelint already offers the exact review location and configurable exceptions.
- `&` is not a simple extra selector level. Sass replaces it with the outer selector, supports suffixing (`&__item`), reversed context (`[dir=rtl] &`), pseudo-classes, interpolation, selector functions, and `@at-root`. Flattening useful `&` nesting merely to lower depth can obscure component state ownership.
- Nested media/supports can be semantically necessary and should remain distinct from selector ancestry. Sass controls generate styles conditionally and are closer to preprocessor generation than executable runtime control; mixing them into one number makes the metric unstable.

### Selector complexity/specificity

Pico owns every `> 8` component finding. Its interpolated parent selectors and grouped modern selectors make the research scalar least authoritative exactly where the values are high. Django/Wayfarer specificity tails reflect IDs and application integration; Primer's component class system has a much lower tail. These are stylesheet architecture choices already expressed through Stylelint configuration, not evidence for a universal Code Guard policy.

### Declaration count

Django's 50-declaration light/root rule contains 49 custom properties; its two 31-declaration dark rules contain 30 each. Pico's 37-declaration light/dark theme mixins are deliberate theme contracts. Wayfarer's `#sidebar-primary` (18) and mobile drawer (17) are more plausible ownership reviews, but their block ranges already provide location and surrounding nested context. Declaration count adds no independent action.

## Stylelint/Sass overlap

Stylelint's authoritative rule set already includes `max-nesting-depth`, `selector-max-specificity`, `selector-max-compound-selectors`, selector combinator/ID/type/attribute policies, invalid-selector checks, and nesting-selector rules. Its `max-nesting-depth` explicitly counts nested rules and at-rules, excludes root at-rules, and supports exceptions for blockless at-rules, pseudo-classes, named at-rules, and named rules. Its specificity implementation follows CSS Nesting semantics, evaluates selector-list members separately, resolves `&` from the parent's maximum specificity, and explicitly documents interpolation/SCSS limitations. Those semantics and configuration surface are specialist responsibilities.

The corpus confirms established ownership: Primer invokes Stylelint over `src/**/*.scss`, uses `@primer/stylelint-config`, and contains targeted `stylelint-disable max-nesting-depth` comments on intentional layout structures. Bootstrap pins Stylelint and a Bootstrap-specific config. Code Guard would either disagree with those project decisions or reproduce their exceptions.

Sass's own documentation advises shallow selectors but also defines nesting, interpolation, and powerful parent-selector behavior as language features. This supports human review but not a second generic linter. Only physical owner span adds a distinct Code Guard question: “has this locally source-ranged styling owner become too large for safe agent modification?” It does not judge selector correctness or style methodology.

References: [Stylelint max nesting depth](https://stylelint.io/user-guide/rules/max-nesting-depth/), [Stylelint selector maximum specificity](https://stylelint.io/user-guide/rules/selector-max-specificity/), [Stylelint rules](https://stylelint.io/user-guide/rules/), [Sass nesting](https://sass-lang.com/documentation/style-rules/), [Sass parent selector](https://sass-lang.com/documentation/style-rules/parent-selector/), and [Tree-sitter error/missing nodes](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html).

## Gaming resistance

- **Meaningless rule splitting:** moving pseudo-states or responsive variants into arbitrary sibling rules lowers parent span without reducing responsibility. Policy must require a real owner boundary and permit `reviewed; coherent; keep`.
- **Metric-only mixins:** extracting declarations into a mixin lowers an individual rule while adding indirection and may duplicate generated output. A mixin is itself a measured owner; extraction is not presumed corrective.
- **Flattening nesting:** repeating expanded selectors can lower depth while obscuring `&` state/modifier relationships. This reinforces rejection of nesting depth.
- **Moving declarations:** theme declarations moved between files/partials retain the same ownership unless the contract actually separates. Declaration count is rejected.
- **Formatting compression:** putting declarations on fewer lines lowers physical span while harming diffs/readability. A future policy must prohibit score-driven formatting and treat formatter configuration as authoritative.

These risks make block size REVIEW-only and opt-in. They do not support FAIL, autofix, exemptions for generated-looking maintained source, or agent-authorized threshold relaxation.

## D27 criteria 1–14

| Criterion | Block physical size | SCSS selector depth | Selector complexity/specificity | Declaration count |
| --- | --- | --- | --- | --- |
| 1 Deterministic anchor | PASS | PASS | QUALIFIED: interpolation resolution is specialist work | PASS |
| 2 Engineering value | PASS: local owner review | QUALIFIED: readable coupling concern | QUALIFIED: style architecture concern | FAIL: adds little beyond owner span |
| 3 Broad applicability | QUALIFIED: CSS/SCSS family | QUALIFIED: SCSS and nested CSS only | QUALIFIED: meaningful but project-specific | QUALIFIED: all style blocks |
| 4 Distinct responsibility | PASS: not offered by Stylelint as agent owner size | FAIL: direct Stylelint rule | FAIL: extensive Stylelint ownership | FAIL: duplicate of accepted span in evidence |
| 5 Stable semantics | PASS with explicit kinds/ranges | QUALIFIED: selector/at-rule/control must remain separate | FAIL for interpolated/nested SCSS without full specialist resolution | PASS |
| 6 Explainability/actionability | PASS: kind/header/range | PASS but already delivered by Stylelint | PASS but already delivered by Stylelint | QUALIFIED: location yes, action weak |
| 7 State model | PASS: REVIEW only | QUALIFIED: lint warning, not Code Guard state | QUALIFIED: lint warning, not Code Guard state | QUALIFIED: REVIEW only possible |
| 8 Signal-to-noise | QUALIFIED at configured high boundary | QUALIFIED at high depth, duplicate concern | FAIL: domain concentration | FAIL: token/theme outliers dominate |
| 9 Threshold/config evidence | CONFIGURABLE ONLY; no universal/default | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE |
| 10 Gaming resistance | MITIGATED only by REVIEW policy | UNACCEPTABLE flattening for Code Guard | UNACCEPTABLE selector rewrites for score | UNACCEPTABLE movement/splitting |
| 11 Scope compatibility | PASS via `ResolvedScope.files` | PASS | PASS | PASS |
| 12 Architecture fit/cost | QUALIFIED: separate style pass; bounded provider possible | FAIL: dependency/semantics duplicate Stylelint | FAIL: specialist parser/semantic cost | QUALIFIED but unnecessary |
| 13 Failure behavior | PASS with explicit bounded recovery/error | QUALIFIED | QUALIFIED | PASS with same provider |
| 14 Portable/testable | PASS: standard library and unittest fixtures | PASS technically | QUALIFIED: authoritative SCSS resolution adds cost | PASS technically |

## Admission decisions

### Rule/block physical size

```text
Deterministic anchor: PASS
Engineering value: PASS
Broad applicability: QUALIFIED
Distinct responsibility: PASS
Stable measurement semantics: PASS
Explainability/actionability: PASS
State model: PASS
Signal-to-noise: QUALIFIED
Threshold/config evidence: CONFIGURABLE ONLY
Gaming risk: MITIGATED
Scope compatibility: PASS
Architecture fit/cost: QUALIFIED
Failure behavior: PASS
Portability/testability: PASS

Decision:
ACCEPT — CONFIGURABLE ONLY
```

No conservative universal REVIEW threshold is justified and default-enabled behavior is explicitly rejected. A later production issue, if opened by maintainers, must require a positive configured boundary, default disabled, strict greater-than REVIEW, never FAIL, and settle kind selection/overlap without changing file LOC.

### SCSS structural/selector nesting depth

```text
Deterministic anchor: PASS
Engineering value: QUALIFIED
Broad applicability: QUALIFIED
Distinct responsibility: FAIL
Stable measurement semantics: QUALIFIED
Explainability/actionability: PASS
State model: QUALIFIED
Signal-to-noise: QUALIFIED
Threshold/config evidence: NOT APPLICABLE
Gaming risk: UNACCEPTABLE
Scope compatibility: PASS
Architecture fit/cost: FAIL
Failure behavior: QUALIFIED
Portability/testability: PASS

Decision:
REJECT / OUT OF SCOPE
```

### Selector complexity/specificity

```text
Deterministic anchor: QUALIFIED
Engineering value: QUALIFIED
Broad applicability: QUALIFIED
Distinct responsibility: FAIL
Stable measurement semantics: FAIL
Explainability/actionability: PASS
State model: QUALIFIED
Signal-to-noise: FAIL
Threshold/config evidence: NOT APPLICABLE
Gaming risk: UNACCEPTABLE
Scope compatibility: PASS
Architecture fit/cost: FAIL
Failure behavior: QUALIFIED
Portability/testability: QUALIFIED

Decision:
REJECT / OUT OF SCOPE
```

### Declaration count/rule fan-out

```text
Deterministic anchor: PASS
Engineering value: FAIL
Broad applicability: QUALIFIED
Distinct responsibility: FAIL
Stable measurement semantics: PASS
Explainability/actionability: QUALIFIED
State model: QUALIFIED
Signal-to-noise: FAIL
Threshold/config evidence: NOT APPLICABLE
Gaming risk: UNACCEPTABLE
Scope compatibility: PASS
Architecture fit/cost: QUALIFIED
Failure behavior: PASS
Portability/testability: PASS

Decision:
REJECT / OUT OF SCOPE
```

## Smallest future architecture and containers

If maintainers authorize a production issue for configured block size, its narrow boundary is:

```text
ResolvedScope.files
    -> .css/.scss applicability
    -> one bounded family-specific style fact pass per file
    -> configured block-size REVIEW guard
    -> common GuardResult / requiredPolicies
```

It must not own discovery, change `scope.exclude`, enter executable `AnalysisFacts`, create generic `ArtifactFacts`/plugins/registries, retain rejected selector/declaration metrics, or alter existing LOC thresholds/applicability. A future provider could consume separately extracted `<style>` regions from Vue/Svelte/Astro/HTML while preserving container-relative source mapping, but this issue admits standalone `.css`/`.scss` only and implements no container extraction.
