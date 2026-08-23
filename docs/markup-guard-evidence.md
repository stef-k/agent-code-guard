# HTML/XML structural guard evidence

## Executive conclusion

Issue #37 evaluated structural element depth, non-root element-subtree physical span, and direct element-child fan-out independently under D27. All three are **REJECT / OUT OF SCOPE**. They are deterministic measurements, but this 556-document / 15,500-element corpus does not show a broadly useful, low-noise review boundary.

- Depth is radically domain-dependent. At `> 10`, the HTML UI corpus alone produces 1,372 findings in all 14 documents, while 344 Android and conventional-HTML documents produce none. At `> 15`, only two trivial nested `div` leaves remain.
- Non-root subtree span still behaves mainly as nested whole-region LOC. Its document maximum has Pearson correlation 0.8641 with file physical lines; large documents produce overlapping ancestor findings rather than distinct responsibilities.
- Fan-out outliers are overwhelmingly legitimate homogeneous collections: dependencies, exported packages/artifacts, table rows, select options, resource values, and declarative layout children.

No production guard, default, configuration, applicability change, or generic facts framework is justified. Existing file LOC remains the appropriate universal size anchor for HTML.

## Candidate definitions

The research scanner defines one finding per element whose value is strictly greater than a candidate boundary; equality passes.

1. **Structural element depth**: the number of authored element ancestors including the element. The outermost authored element is depth 1. Document, declaration, doctype, text, comments, CDATA, attributes, and raw script/style text do not add depth.
2. **Non-root subtree physical span**: inclusive physical lines from an element's authored start tag through its matching end tag. Nested content counts. A same-line or empty element spans one line. Outermost elements are excluded from finding volume, but `body` and other near-root elements are not silently suppressed.
3. **Direct-child fan-out**: immediate element children only. Text, comments, CDATA, attributes, and other tokens do not count.

LF and CRLF use the same physical-line semantics, an unterminated final record counts, and findings retain tag plus start/end line in source order. Script and style are opaque elements: their contents are not reinterpreted.

## Parser/provider and malformed-file semantics

### HTML

The evidence scanner selects Python `html.parser.HTMLParser` (PSF-licensed standard library) as the smallest research provider. It supplies deterministic authored start positions, recognizes void elements, treats script/style bodies as raw data, and requires no package or platform addition. The scanner maintains an authored-element stack, closes through a matching end tag, records unmatched/implicitly closed items as recovery telemetry, and bounds still-open elements at EOF. Malformed HTML is therefore measured through deterministic tolerant recovery; it is never turned into a validity finding.

This is deliberately an authored-source event tree, not a browser DOM and not a claim of full HTML5 tree-construction semantics. Optional-tag browser implications can differ. Only 2 of 212 HTML documents required stack recovery, both MDN picture-in-picture examples, so this limitation did not drive the observed boundaries. If a different markup metric were admitted later, a production HTML provider would have to preserve source ranges while implementing an explicitly tested HTML5 recovery contract. Unsupported encoding or inability to produce bounded structure would be a structured measurement error, not a silent skip.

The already-pinned `tree-sitter-language-pack==1.14.3` exposes HTML and XML grammars with byte/point ranges and an MIT-family dependency footprint. It was evaluated first. A small ordinary MDN page (`media/web-dictaphone/index.html`) caused a repeatable Windows process access violation during HTML node/range traversal with the pinned binding, so it was not used as the evidence authority. `html5lib` would improve browser-like HTML recovery but adds a dependency and does not provide the required original end ranges. `lxml` similarly adds binary/package cost and its recovered DOM is not a source-range contract. Neither is justified for rejected candidates.

### XML

The evidence scanner selects Python's Expat binding (standard library) separately. It preserves ordered start/end line events, qualified names, declarations, doctypes, comments, CDATA boundaries, and empty-element structure without a new dependency. XML is strict: any Expat syntax error is a structured measurement error with line/column and no recovered metrics. A selected supported malformed XML artifact must never be silently skipped. All 344 selected XML documents parsed; inapplicable generated/vendor XML was excluded before parsing by the corpus manifest, analogous to future runner-owned scope.

These providers belong only to research tooling. No markup is routed through executable `AnalysisFacts`.

## Pinned corpus and methodology

Disposable shallow clones were created outside the repository. Selection retained manually maintained source and excluded build/generated/vendor/test-resource material. Raw manifests and dumps are not committed.

| Corpus | SHA | Selected | Role and selection |
| --- | --- | ---: | --- |
| `mdn/dom-examples` | `5419e769b8cae4f94e6634668cdaa3c33b0127cb` | 198 HTML | Conventional manually maintained API examples; all HTML/HTM, excluding vendor/dist/build/coverage |
| `StartBootstrap/startbootstrap-sb-admin-2` | `f0309881ef82794a1bd6257cd321801bc38a0f3d` | 14 HTML | HTML-heavy UI, including tables, cards, forms, navigation, and utilities; repository-root authored pages |
| `android/sunflower` | `2a357a31551bb53f3fe80382a9ce6d30bcc8b960` | 6 XML | Current layouts/manifests/default resource values; localized/generated/drawable material excluded |
| `android/views-widgets-samples` | `2238cc873501f9cda63605051de11832bb736a8a` | 146 XML | Mature declarative layouts/manifests, including ConstraintLayout/MotionLayout noise controls |
| `apache/maven` | `540897d3d3c329a38e4df9648249c9d407dbc8c2` | 192 XML | Maintained POMs, site/assembly/config and main-resource descriptors; tests, generated and targets excluded |

The aggregate is 556 documents, 15,500 elements, zero XML measurement errors, and two tolerant HTML recovery documents. Candidate boundaries were selected before inspection: depth 6/8/10/12/15; span 50/100/200/300/500 lines; fan-out 10/20/30/50/100 children. Percentiles describe the corpus; they do not choose policy.

## Distributions

| Document maximum | Median | P75 | P90 | P95 | P99 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Physical file lines | 44 | 73 | 134 | 206 | 599 | 1,300 |
| Element depth | 4 | 5 | 8 | 9 | 14 | 16 |
| Non-root subtree span | 17 | 38 | 94 | 152 | 500 | 900 |
| Direct-child fan-out | 4 | 7 | 11 | 15 | 46 | 87 |

Per-corpus maxima show why aggregate percentiles are not universal policy:

| Corpus | Documents / elements | Depth median / max | Span median / max | Fan-out median / max |
| --- | ---: | ---: | ---: | ---: |
| MDN | 198 / 3,913 | 4 / 9 | 30 / 180 | 5 / 31 |
| Bootstrap UI | 14 / 3,253 | 14 / 16 | 483 / 900 | 14 / 57 |
| Sunflower | 6 / 61 | 2 / 5 | 3 / 36 | 3 / 21 |
| Android Views | 146 / 1,013 | 2 / 6 | 12.5 / 174 | 2 / 41 |
| Maven | 192 / 7,260 | 4 / 12 | 13 / 514 | 6 / 87 |

## Actual future finding volume

Each cell is `findings / affected documents / documents with multiple findings`.

### Depth

| Corpus | > 6 | > 8 | > 10 | > 12 | > 15 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MDN | 391/23/20 | 23/4/4 | 0/0/0 | 0/0/0 | 0/0/0 |
| Bootstrap UI | 2,540/14/14 | 1,911/14/14 | 1,372/14/14 | 509/13/12 | 2/2/0 |
| Sunflower | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Android Views | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Maven | 1,230/36/33 | 401/14/13 | 61/6/5 | 0/0/0 | 0/0/0 |
| **All** | **4,161/73/67** | **2,335/32/31** | **1,433/20/19** | **509/13/12** | **2/2/0** |

At `> 10`, findings are 9.25% of all elements, concentrated into 20 documents and mostly hundreds per HTML page. `> 12` still reports 509 authored elements in one coherent UI family. `> 15` finds only two three-line nested `div` leaves in `index.html:428` and `cards.html:419`, which are poor responsibility anchors.

### Non-root subtree span

| Corpus | > 50 | > 100 | > 200 | > 300 | > 500 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MDN | 97/47/36 | 36/23/12 | 0/0/0 | 0/0/0 | 0/0/0 |
| Bootstrap UI | 143/14/13 | 91/11/11 | 62/11/11 | 44/11/11 | 12/4/4 |
| Sunflower | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Android Views | 23/15/5 | 3/3/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Maven | 87/27/14 | 31/13/6 | 11/6/3 | 3/1/1 | 2/1/1 |
| **All** | **350/103/68** | **161/50/29** | **73/17/14** | **47/12/12** | **14/5/5** |

Multiple findings dominate every serious high boundary because nested ancestors span the same content. At `> 500`, all five documents have multiple findings. Excluding only the document root does not prevent `body` and wrapper chains from restating file size. Document LOC versus maximum non-root subtree span has Pearson correlation 0.8641.

### Fan-out

| Corpus | > 10 | > 20 | > 30 | > 50 | > 100 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MDN | 15/14/1 | 1/1/0 | 1/1/0 | 0/0/0 | 0/0/0 |
| Bootstrap UI | 15/11/3 | 1/1/0 | 1/1/0 | 1/1/0 | 0/0/0 |
| Sunflower | 2/2/0 | 1/1/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Android Views | 5/5/0 | 2/2/0 | 1/1/0 | 0/0/0 | 0/0/0 |
| Maven | 51/38/6 | 17/13/3 | 12/9/3 | 4/3/1 | 0/0/0 |
| **All** | **88/70/10** | **22/18/3** | **15/12/3** | **5/4/1** | **0/0/0** |

Low volume does not equal signal. Every inspected high outlier is a collection whose peers naturally belong together.

## Boundary and coherent-keep inspection

### Depth

- Below: Android `constraint_example_x1.xml` reaches depth 5 while expressing a coherent ConstraintLayout; flattening would discard useful hierarchy.
- Around: MDN pages at depth 8–9 are ordinary nested examples. Maven depth 10–12 comes from plugin/profile/configuration ownership, not executable control flow.
- Above/outliers: the Bootstrap pages' depth 14–16 is produced by navigation, cards, dropdowns, and utility wrappers. Hundreds of descendant findings repeat the same ancestry; the two depth-16 leaves are not actionable decomposition boundaries.

### Subtree span

- Below: Android `lots_of_cards.xml` contains a coherent 174-line declarative layout. It is large but locally navigable and is a deliberate repetitive-layout noise control.
- Around 200: eleven near-identical Bootstrap `nav` regions span 201–203 lines, and Maven dependency blocks span 186–219 lines. These are coherent shared-navigation and dependency collections.
- Above/outliers: Bootstrap `tables.html` has a 900-line `body` plus overlapping 852/728/712-line wrappers and a legitimate 57-row table. Maven's root POM has 514/510-line dependency-management/dependencies ancestors. The metric reports size repeatedly without identifying an independent responsibility beyond LOC.

### Fan-out

- Below/around 20: MDN list/section examples, Android resources, Maven modules/properties, and Bootstrap button collections are coherent peers.
- Above: MDN's 31-child `select` is an option collection; Android's 41-child `LinearLayout` is the intentional `lots_of_cards` demo; Bootstrap's 57-child `tbody` is tabular data.
- Outliers: Maven's 87 dependencies, 74 exported packages, and 59 exported artifacts are mature descriptor lists. Splitting or wrapping them only to reduce a count would harm navigation.

## Specialist-tool overlap and gaming

None of the candidates should be rescued with tag exemptions, framework tables, or semantic guesses. HTML validity, accessibility, semantic elements, schema conformance, formatting, duplicate IDs, and security remain with specialist tools.

- Depth invites flattening semantic hierarchy, removing useful wrappers, or moving content into opaque/generated fragments.
- Span invites meaningless file/component extraction and duplicated wrappers while the responsibility remains unchanged.
- Fan-out invites bucket wrappers that add depth and obscure a coherent ordered collection.

All hypothetical findings would have to be REVIEW-only and allow `reviewed; coherent; keep`; no FAIL evidence exists. The stronger conclusion is that routine coherent keeps dominate, so no policy should be created.

## D27 criteria 1–14

| Criterion | Depth | Non-root subtree span | Fan-out |
| --- | --- | --- | --- |
| 1 Deterministic anchor | PASS | PASS | PASS |
| 2 Engineering value | UNCLEAR: deep does not locate a responsibility | FAIL: mostly repeated region size | FAIL: collections dominate |
| 3 Broad applicability | FAIL: format/domain ranges diverge | QUALIFIED: measurable, not equally useful | FAIL: collection-heavy domains dominate |
| 4 Distinct responsibility | QUALIFIED: not a validator, but weak value | FAIL: duplicates LOC strongly | QUALIFIED: distinct count, no useful prompt |
| 5 Stable semantics | QUALIFIED: authored depth differs from browser DOM | PASS | PASS |
| 6 Explainability/actionability | FAIL: floods descendants | FAIL: overlapping ancestors | FAIL: coherent collection is the location |
| 7 State model | QUALIFIED: REVIEW-only possible | QUALIFIED: REVIEW-only possible | QUALIFIED: REVIEW-only possible |
| 8 Signal-to-noise | FAIL | FAIL | FAIL |
| 9 Threshold/config evidence | UNCLEAR; neither default nor useful opt-in shown | UNCLEAR; thresholds track LOC/domain | UNCLEAR; low-volume outliers remain noise |
| 10 Gaming resistance | UNACCEPTABLE flattening | UNACCEPTABLE fragmentation | UNACCEPTABLE bucket wrappers |
| 11 Scope compatibility | PASS via `ResolvedScope.files` | PASS | PASS |
| 12 Architecture fit/cost | QUALIFIED; separate markup pass required | QUALIFIED | QUALIFIED |
| 13 Failure behavior | QUALIFIED by tolerant HTML/strict XML contracts | QUALIFIED | QUALIFIED |
| 14 Portable/testable | PASS with standard-library research providers | PASS | PASS |

## Admission decisions

### Structural element depth

```text
Deterministic anchor: PASS
Engineering value: UNCLEAR
Broad applicability: FAIL
Distinct responsibility: QUALIFIED
Stable measurement semantics: QUALIFIED
Explainability/actionability: FAIL
State model: QUALIFIED
Signal-to-noise: FAIL
Threshold/config evidence: UNCLEAR
Gaming risk: UNACCEPTABLE
Scope compatibility: PASS
Architecture fit/cost: QUALIFIED
Failure behavior: QUALIFIED
Portability/testability: PASS

Decision:
REJECT / OUT OF SCOPE
```

### Large element/subtree physical span

```text
Deterministic anchor: PASS
Engineering value: FAIL
Broad applicability: QUALIFIED
Distinct responsibility: FAIL
Stable measurement semantics: PASS
Explainability/actionability: FAIL
State model: QUALIFIED
Signal-to-noise: FAIL
Threshold/config evidence: UNCLEAR
Gaming risk: UNACCEPTABLE
Scope compatibility: PASS
Architecture fit/cost: QUALIFIED
Failure behavior: QUALIFIED
Portability/testability: PASS

Decision:
REJECT / OUT OF SCOPE
```

### Direct-child/fan-out size

```text
Deterministic anchor: PASS
Engineering value: FAIL
Broad applicability: FAIL
Distinct responsibility: QUALIFIED
Stable measurement semantics: PASS
Explainability/actionability: FAIL
State model: QUALIFIED
Signal-to-noise: FAIL
Threshold/config evidence: UNCLEAR
Gaming risk: UNACCEPTABLE
Scope compatibility: PASS
Architecture fit/cost: QUALIFIED
Failure behavior: QUALIFIED
Portability/testability: PASS

Decision:
REJECT / OUT OF SCOPE
```

## Architecture and future containers

Because no candidate is admitted, there is no future guard family boundary or threshold/default-enable decision. If later evidence admits a different markup-specific fact, the smallest shape remains:

```text
ResolvedScope.files
    -> markup applicability
    -> one concrete markup parse/fact pass per file
    -> admitted markup guard(s)
    -> common GuardResult / requiredPolicies
```

It must not own discovery, enter executable `AnalysisFacts`, or create `ArtifactFacts`, plugins, or a registry. A source-ranged markup provider could later consume regions extracted from Vue/Razor/Svelte/Astro, but issue #37 supplies no admitted fact to integrate and implements none.
