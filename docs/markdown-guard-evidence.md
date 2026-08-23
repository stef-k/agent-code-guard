# Markdown Structured-Artifact Guard Evidence

## 1. Executive conclusion

**Overall outcome: ACCEPT.** Markdown belongs in Agent Code Guard through two
separate, conservative inspection anchors, but this research PR activates
nothing:

| Candidate | Outcome | Future universal default | Future default enabled | State |
|---|---|---:|---:|---|
| Document physical lines | **ACCEPT** | REVIEW when `> 800` | Yes | PASS / REVIEW |
| Document nonblank lines | Reject as the primary variant | — | — | — |
| Direct-content section physical span | **ACCEPT** | REVIEW when `> 200` | Yes | PASS / REVIEW |
| Heading-subtree span | **REJECT** | — | — | — |
| Maximum heading depth | **REJECT / OUT OF SCOPE** | — | — | — |

REVIEW means **inspect structure**, not “split automatically.” A review may
conclude `reviewed; coherent; keep`. There is no FAIL threshold. Both admitted
defaults should permit a positive project override and explicit disablement.
The exact threshold passes; only a greater measurement reviews.

The evidence is 912 Markdown documents from five heterogeneous repositories.
At the proposed boundaries, 59 documents (6.47%) review for document size and
29 (3.18%) review for direct section size. The findings include genuine
navigation/cohesion prompts and deliberate coherent keep cases. This is an
acceptable REVIEW workload, not a claim that either number is a quality law.

## 2. Why Markdown was evaluated

Markdown is the first structured candidate because repositories routinely put
overview, design, runbook, specification, RFC, and contributor knowledge in it.
Agents frequently retrieve or extend only one topic. Ever-growing files and
heading-delimited blocks increase navigation and irrelevant context even when
the prose is valid Markdown. The concern is maintainability structure, not
spelling, grammar, links, accessibility, or formatting style.

## 3. Candidate metrics

The research tool compared:

- all physical document lines and nonblank physical document lines;
- the largest heading-subtree section and largest direct-content section;
- maximum heading level, only long enough to test admission; and
- physical direct-section span with fenced lines removed, as one bounded noise
  comparison rather than a proposed third guard.

All counts use logical physical records: empty file is zero, `x` and `x\n` are
one, LF and CRLF are equivalent, and a final unterminated line counts once.
Whitespace-only lines are blank. Preamble belongs to the document but not to a
synthetic section. A headingless document has no sections.

## 4. Structural parsing semantics

`research/markdown_guard_sample.py` is a research-only bounded scanner. It is
not imported by production and adds no install dependency.

Its explicit top-level outline contract is:

- ATX headings allow zero to three leading spaces, one to six unescaped `#`
  markers, required whitespace/end after the opening marker, and optional
  whitespace-separated closing hashes;
- Setext H1/H2 recognizes a single eligible nonblank title line followed by an
  `=`/`-` underline with zero to three leading spaces;
- backtick and tilde fences require at least three identical markers, zero to
  three leading spaces, same-marker closure at least as long as the opener, and
  ignore all heading-looking content while open;
- a backtick fence info string containing a backtick is not an opener;
- an unclosed fence deterministically consumes to EOF and is reported, not
  treated as invalid Markdown;
- four-space-indented and escaped heading-looking lines are not headings;
- repeated names stay distinct through ranges; Unicode text is preserved; and
- undecodable UTF-8 raises a deterministic read error rather than being skipped.

The scanner deliberately measures the document's top-level Markdown outline.
It does not promote headings nested in block quotes or list items into that
outline, interpret raw HTML headings, or implement multi-line Setext paragraph
titles. Those constructs remain content. The future production contract should
retain these bounds unless a fixture demonstrates that broader container
semantics materially improve the guard. This is CommonMark-informed, not a
claim to be a complete CommonMark parser.

## 5. Section ownership models

| Model | Ownership | What it measures | Evidence result |
|---|---|---|---|
| Heading subtree | Heading through the next heading of equal or shallower level | An entire structural branch | Repeats document size, especially for top-level headings; noisy |
| Direct content | Heading through immediately before the next heading of any level | One locally undivided documentation unit | Distinct and actionable |

Subtree ranges intentionally overlap. Direct ranges do not. Both include the
heading syntax; a Setext heading includes its title and underline. Adjacent
headings therefore create a one-line ATX or two-line Setext section, not a
zero-line finding.

The subtree median was 95 lines, but even `>300` reviewed 151 documents
(16.56%). Root headings often owned nearly the whole file: OpenTelemetry's
2,012-line metrics SDK produced a 2,007-line subtree. That says little beyond
the already clearer document measurement. Direct content instead isolates a
single block such as Wayfarer's 242-line testing runbook or ripgrep's
1,063-line FAQ.

## 6. Corpus and pinned SHAs

All repositories were cloned through `gh` outside this repository and removed
after analysis. Scope was recursive `*.md` and `*.markdown`; Git contents were
the exact checked-out commits below.

| Repository | Exact SHA | Files | Role/category notes and exclusions |
|---|---|---:|---|
| `stef-k/agent-code-guard` | `e6bfcd5ee18dfa8ce21f153c6da56a8f276845b1` | 14 | README, admission/design/evidence docs, agent skill/policy Markdown; no exclusions |
| `stef-k/Wayfarer` | `264e74d9e5b9f93c83ce1eff659b399b2eb22cf6` | 29 | README, architecture, runbooks, process docs; excluded `wwwroot/lib/**` vendored docs (1 file) |
| `BurntSushi/ripgrep` | `3fce3b5bb0236da2df6d99672afb8a719642eca7` | 22 | README, guide, FAQ, contributor/process docs; excluded `CHANGELOG.md` |
| `open-telemetry/opentelemetry-specification` | `1377f53b2bc0683c45169b8f20fd973eb4d59419` | 193 | specification, OTEP/design, process and README documents; excluded `CHANGELOG.md` |
| `rust-lang/rfcs` | `354518a8c9025f40be6f730452c1bfe71a12dc22` | 654 | long-form RFC/specification corpus plus repository process docs; no generated or vendored tree identified |

The corpus deliberately over-represents specification/RFC documents so that a
universal rule must survive coherent long-form material. No sampled file used
the `.markdown` suffix. A first production slice should therefore support
`.md`; `.markdown` remains a deterministic research input but lacks corpus
evidence for default applicability.

## 7. Document-size distributions

### Aggregate

| Variant | n | Median | P75 | P90 | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| All physical lines | 912 | 182 | 370 | 657 | 881 | 1,722 | 2,205 |
| Nonblank physical lines | 912 | 136 | 273 | 508 | 723 | 1,310 | 1,809 |

### Physical lines by corpus

| Corpus | n | Median | P75 | P90 | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Agent Code Guard | 14 | 136 | 317 | 385 | 387 | 387 | 387 |
| Wayfarer | 29 | 132 | 250 | 443 | 608 | 763 | 763 |
| ripgrep | 22 | 33 | 57 | 541 | 1,025 | 1,063 | 1,063 |
| OpenTelemetry | 193 | 136 | 318 | 676 | 1,000 | 1,676 | 2,012 |
| Rust RFCs | 654 | 202.5 | 391 | 661 | 916 | 1,774 | 2,205 |

## 8. Document-size candidate thresholds

| Physical boundary | Reviews | Rate |
|---:|---:|---:|
| `>400` | 202 | 22.15% |
| `>500` | 147 | 16.12% |
| `>600` | 105 | 11.51% |
| **`>800`** | **59** | **6.47%** |
| `>1,000` | 37 | 4.06% |
| `>1,200` | 22 | 2.41% |

The selected `>800` boundary is conservative while still catching large
ordinary docs and extreme structured specs. Per corpus it reviews 0% Agent
Code Guard, 0% Wayfarer, 9.09% ripgrep, 7.25% OpenTelemetry, and 6.57% Rust
RFCs. This is broad rather than driven by one repository.

The closest nonblank comparison, `>600`, reviewed 62 documents (6.80%). The
upper-tail membership and rates were similar. Nonblank lines make formatting
compression an especially direct gaming path and discount real scrolling and
navigation surface. Blank lines are not demonstrated noise, so all physical
lines are the simpler and more honest measurement.

## 9. Document boundary inspections

| Position | Example | Measurement | Inspection |
|---|---|---:|---|
| Below | OpenTelemetry `trace/tracestate-probability-sampling.md` | 497 | Coherent specification with usable headings; no split needed, but below the conservative default |
| Around middle candidate | Rust RFC `3513-gen-blocks.md` | 803 | Many language-by-language prior-art subsections; navigation is material and REVIEW is useful even if retained |
| Moderately above | Rust RFC `2091-inline-semantic.md` | 1,199 | Long semantic proposal; structured but sufficiently large that extension deserves an outline check |
| Extreme | Rust RFC `1398-kinds-of-allocators.md` | 2,205 | Formal, intentionally comprehensive RFC; coherent keep is plausible, but targeted retrieval cost is real |
| Extreme | OpenTelemetry `specification/metrics/sdk.md` | 2,012 | Mature multi-topic specification with a 2,007-line root subtree; document REVIEW is clearer than subtree REVIEW |

Total size is coarse, but not redundant with direct section size. A 2,000-line
specification can have disciplined 100-line local units while still imposing a
large navigation and context surface. The finding must point to the whole file
and ask whether its outline, responsibility, and extension location remain
clear; it must not demand a split.

## 10. Section-size distributions

Per document, the metric below is the maximum section span.

| Ownership model | n | Median | P75 | P90 | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Direct content | 912 | 46 | 77 | 121 | 158 | 265 | 1,063 |
| Heading subtree | 912 | 95 | 211 | 395 | 550 | 1,258 | 2,007 |

## 11. Section-size candidate thresholds

### Direct-content span

| Boundary | Reviews | Rate |
|---:|---:|---:|
| `>100` | 129 | 14.14% |
| `>120` | 95 | 10.42% |
| `>150` | 55 | 6.03% |
| `>160` | 44 | 4.82% |
| **`>200`** | **29** | **3.18%** |
| `>240` | 17 | 1.86% |
| `>300` | 9 | 0.99% |

At `>200`, per-corpus rates are 0% Agent Code Guard, 3.45% Wayfarer, 9.09%
ripgrep, 3.11% OpenTelemetry, and 3.06% Rust RFCs. The higher ripgrep rate is
two deliberately large user-facing documents in a small 22-file set, not a
large warning count.

### Heading-subtree span

| Boundary | Reviews | Rate |
|---:|---:|---:|
| `>200` | 246 | 26.97% |
| `>300` | 151 | 16.56% |
| `>400` | 90 | 9.87% |
| `>500` | 56 | 6.14% |
| `>800` | 25 | 2.74% |

Only a very high subtree boundary produces a conservative rate, at which point
it is an indirect, harder-to-explain duplicate of document size. It is rejected
rather than shipped alongside direct content.

## 12. Section boundary inspections

| Position | Example section | Span | Inspection |
|---|---|---:|---|
| Below | Rust RFC 2011 `Generic assert` local block | 80 | Compact proposal unit; no signal needed |
| Around 120 | Rust RFC 0216 `Detailed design` | 121 | Long API/code exposition but one coherent design; useful evidence against a low default |
| Around 160 | Rust RFC 2580 `Reference-level explanation` | 161 | Several API definitions and code; inspectable, often coherent; supports a more conservative boundary |
| Around selected | Wayfarer `docs/22-Testing.md`, `Testing` | 242 | One heading owns policies, environment discovery, databases, browser preflight, commands, and CI; meaningful headings would improve targeted retrieval |
| Above | Rust RFC 1479 `Detailed design` | 416 | Large code-heavy design; REVIEW useful, but retaining it as one formal unit is defensible |
| Extreme | ripgrep `FAQ` | 1,063 | Questions use raw HTML headings, outside the bounded outline contract; the huge local unit is real to Markdown-outline tooling and warrants inspection, though conversion may have compatibility costs |
| Extreme keep | OpenTelemetry profiles `Proto Definition` | 565 | 432 fenced lines dominate a coherent protocol definition; explicit `reviewed; coherent; keep` |

Direct content best answers “does this local documentation unit deserve
inspection?” It finds the mixed-responsibility testing runbook and the unusual
single-section FAQ, while policy can retain formal/code-heavy units.

## 13. Heading-depth evaluation

Maximum depth had median 3, P75/P90 4, P95/P99 5, and max 6. Rates were 31.91%
above 3, 7.24% above 4, and 0.88% above 5. Inspection did not show that level 5
itself causes maintainability difficulty. Deep hierarchy was often appropriate
in specifications; shallow files could still be monolithic.

This overlaps mature lint/style and accessibility concerns. markdownlint MD001
checks heading increments, while MD025/MD041 cover top-level heading
conventions. Google's heading guidance emphasizes descriptive, logical
hierarchy, and GitLab's depth guidance is partly tied to its own sidebar.
Agent Code Guard would add no stable maintainability meaning by warning on a
numerical heading level. **Heading depth is rejected.**

## 14. Coherent/no-refactor examples

- OpenTelemetry profiles `Proto Definition`: long embedded protocol definition;
  splitting the code solely for the metric would reduce usefulness.
- Rust RFC 1479 `Detailed design`: one formal design with extensive example
  code; headings may help, but a reviewed keep is legitimate.
- Rust RFC 1398: a 2,205-line exhaustive allocator proposal; whole-document
  REVIEW is valuable before extension even if archival coherence wins.
- OpenTelemetry log data model `Elastic Common Schema`: a large compatibility
  reference/mapping; separation may damage cross-reference value.
- Rust RFC 0809 `Appendix A: sample operator traits`: large reference code whose
  single-topic nature is clearer than an artificial outline.

These are useful REVIEWs with a no-change conclusion, not metric failures.
Policy must make that outcome first-class.

## 15. Fenced-code, table, and list noise

Counting fenced code normally produced 29 direct-section reviews at `>200`.
Removing fenced lines reduced that to 11 (1.21%); at `>160`, it fell from 44
to 18. Examples crossing below included the OpenTelemetry profile proto (565
to 133), Rust Unix socket detailed design (416 to 65), and ripgrep README (218
to 131).

That difference is real, but not a reason to discount code. Large examples
still consume navigation/context, code-exclusion would invite hiding content in
fences, and the remaining prose-only count would understate a section's actual
surface. The selected metric counts all lines and uses REVIEW policy for
coherent examples.

Long tables, bullet lists, checklists, and compatibility/reference mappings
also produced legitimate long units. No deterministic table/list discount
improved the meaning enough to justify another semantic dimension. No AST
complexity or content-type exception is proposed.

## 16. External-tool precedent

Authoritative references were checked for overlap:

- [CommonMark 0.31.2 headings](https://spec.commonmark.org/0.31.2/#atx-headings),
  [Setext headings](https://spec.commonmark.org/0.31.2/#setext-headings), and
  [fenced code](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) define
  deterministic structural behavior, not size policy.
- [markdownlint rules](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md)
  cover heading order/style, whitespace, duplicates, line length, fences, and
  links, but contain no maximum document-line or heading-delimited section-size
  rule. [MD013](https://github.com/DavidAnson/markdownlint/blob/main/doc/md013.md)
  is per-line character length, not artifact size.
- [Google developer documentation heading guidance](https://developers.google.com/style/headings)
  supports descriptive headings and logical hierarchy but gives no page or
  section line maximum.
- [GitLab documentation style guidance](https://docs.gitlab.com/development/documentation/styleguide/)
  connects topic structure with scanning/findability, but its depth guidance
  partly reflects GitLab navigation and supplies no physical-span threshold.
- [Vale occurrence checks](https://vale.sh/docs/checks/occurrence) are generic,
  author-configured style primitives, not document/section size precedent.

There is little mature threshold precedent to copy. That weakens any claim of
mathematical universality, but supports distinct responsibility: the admitted
metrics are navigation/reasoning guardrails, not duplicated Markdown lint.

## 17. Agent usefulness

The findings give agents a deterministic pause before appending to an already
large README, design, runbook, or local section. The expected benefit is easier
targeted retrieval, clearer topic boundaries, less irrelevant context, and
less “append forever” behavior. The corpus demonstrates those situations, but
does not measure exact token savings, so none are claimed.

Costs are coherent-spec reviews, pressure to add headings mechanically, doc
fragmentation, and warning fatigue. Conservative defaults, REVIEW-only state,
exact ranges, and explicit keep language make those costs acceptable.

## 18. Gaming resistance

Policy for both metrics must prohibit:

- removing blank lines or compressing formatting merely to lower document size;
- adding meaningless headings merely to lower direct-section size;
- mechanically splitting a coherent document across files;
- moving content without improving ownership/navigation; and
- hiding prose in fences (one reason fenced lines remain counted).

Agents should optimize for clearer navigation and responsibility, never the
number itself. Overrides and disablement require ordinary user/project
authority; agents must not weaken configuration merely to silence a result.

## 19. Generated and reference documentation

Generated, vendored, changelog-dump, and dependency documentation should
normally be excluded through existing `scope.exclude`, after Git-ignore-aware
selection and before guard applicability. Explicitly retained reference/spec
documents remain eligible: their size still justifies inspection, and policy
allows a coherent keep. Role-specific production thresholds or generated-file
heuristics would create ambiguous policy and are rejected.

The corpus excluded one vendored Wayfarer doc and two changelogs. It retained
formal RFCs, specifications, protocol definitions, reference tables, and long
examples deliberately as noise controls.

## 20. Admission criteria 1–14

| # | Criterion | Document physical size | Direct section size | Subtree size | Heading depth |
|---:|---|---|---|---|---|
| 1 | Deterministic anchor | PASS | PASS | PASS | PASS |
| 2 | Engineering value | PASS: navigation/context surface | PASS: local cohesion/navigation | QUALIFIED: mostly repeats document | FAIL: depth alone weak |
| 3 | Broad applicability | PASS across sampled roles/repos | PASS across sampled roles/repos | QUALIFIED | FAIL/qualified by style |
| 4 | Distinct responsibility | PASS: no mature lint equivalent | PASS: no mature lint equivalent | FAIL: duplicates document metric | FAIL: lint overlap |
| 5 | Stable semantics | PASS: physical records | PASS: next heading of any level | PASS but coarse | PASS measurement, weak meaning |
| 6 | Explainable/actionable | PASS: exact file/range | PASS: heading and exact range | QUALIFIED: overlapping/root spans | QUALIFIED |
| 7 | Useful state model | PASS/REVIEW only | PASS/REVIEW only | Would be REVIEW only | No useful Code Guard state |
| 8 | Signal-to-noise | PASS at `>800` | PASS at `>200` | FAIL at useful boundaries | FAIL/weak |
| 9 | Threshold/config evidence | DEFAULT 800 + override/disable | DEFAULT 200 + override/disable | NOT APPLICABLE | NOT APPLICABLE |
| 10 | Gaming resistance | MITIGATED by policy; count blanks | MITIGATED; count all content | Similar but no value | Meaningless shallowing risk |
| 11 | Scope compatibility | PASS through `ResolvedScope.files` | PASS through same facts | PASS technically | PASS technically |
| 12 | Architecture fit/cost | PASS with bounded separate facts | PASS from same scan | FAIL necessity/YAGNI | FAIL necessity |
| 13 | Failure behavior | PASS: UTF-8 error; permissive EOF fence | PASS: same | PASS technically | PASS technically |
| 14 | Portable/testable | PASS; stdlib-only fixtures | PASS; stdlib-only fixtures | PASS technically | PASS technically |
| | **Decision** | **ACCEPT** | **ACCEPT** | **REJECT** | **REJECT / OUT OF SCOPE** |

The rejected metrics remain explicit; they are not hidden inside the overall
Markdown ACCEPT.

## 21. Threshold and default-enable conclusions

For a future production slice:

| Guard | Universal default? | Default enabled? | Override? | Disable? | FAIL? |
|---|---:|---:|---:|---:|---:|
| Markdown document physical size | Yes, 800 | Yes | Positive integer | Yes | No |
| Markdown direct section physical size | Yes, 200 | Yes | Positive integer | Yes | No |

These are conservative inspection guardrails in the D30 philosophy, not
mathematical quality laws. Exact thresholds pass. A finding above either value
asks the agent to inspect responsibility and navigation, and authorizes a
documented coherent keep.

## 22. Architecture recommendation

The smallest future shape is:

```text
ResolvedScope.files
    -> .md applicability
    -> one lazy bounded Markdown scan per file
    -> immutable document and direct-section facts
    -> document-size and section-size guards
    -> GuardResult / requiredPolicies
```

Do not add Markdown to `DEFAULT_INCLUDE_EXTENSIONS` for LOC, reuse executable
`AnalysisFacts`, or create `ArtifactFacts`. A concrete immutable Markdown
document fact should carry path and physical count plus range-qualified heading
sections; a section fact needs heading text, level, source range, and physical
span. Repeated headings are disambiguated by range. Rejected subtree/depth
measurements should not survive into production facts.

The scanner should be lazy and separate because Markdown parse/failure
semantics differ from executable syntax. The research implementation indicates
that no production dependency is required. If future fixtures expose material
container/CommonMark gaps, reconsider an established parser then, with license,
maintenance, wheels, dependency tree, and cross-platform cost assessed before
changing the contract.

One later issue should deliver the complete vertical slice: facts/scanner,
configuration, runner orchestration over final scope, result/text/JSON output,
required policies, tests, documentation, packaging, and three-platform CI. No
generic registry/plugin groundwork is justified.

## 23. Final admission outcome

**ACCEPT** Markdown document physical size and direct-content section physical
size for a future production implementation. **REJECT** document nonblank lines
as the primary measurement, heading-subtree section size as redundant/noisy,
and heading depth as style-lint territory. Do not ship production behavior in
this evidence PR.

## 24. Remaining risks

- The corpus is large but dominated numerically by Rust RFCs; per-corpus rates
  reduce, not eliminate, that weighting risk.
- Raw HTML headings (ripgrep FAQ), container-nested headings, and multi-line
  Setext titles are deliberately outside the bounded outline contract. Future
  fixtures should preserve the contract or prove a material reason to expand it.
- `.markdown` had zero corpus examples; default applicability is not yet earned.
- Coherent specifications will review by design. Warning fatigue depends on
  findings and policy making `reviewed; coherent; keep` cheap and explicit.
- Thresholds should be revisited only with new representative evidence, not
  tuned to silence a single repository.
