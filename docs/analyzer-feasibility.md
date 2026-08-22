# Callable Analyzer Feasibility

This report records the issue #4 research prototype. It is evidence for a later
production design, not an enabled Code Guard feature. The canonical LOC guard
and its policy are unchanged.

## Questions and measurement definitions

The prototype asks whether one parse can provide stable named-callable ranges
and enough syntax facts for three independent metrics in Python, Go, Kotlin,
and C#.

### Callable scope and identity

Included callables are named top-level functions, named methods, constructors,
and named local/nested functions where the language supports them. Named
expression-bodied declarations are included. C# accessors and all anonymous
lambdas/closures are excluded. A nested named callable receives its own finding;
its control flow is not charged to the enclosing callable.

Identity is lexical rather than symbol-resolved and is always paired with path
and range:

- Python: `module.Type.method` or `module.outer.local`;
- Go: `package.function` or `package.Receiver.method`;
- Kotlin: `package.Type.method` or `package.outer.local`;
- C#: `Namespace.Type.Method`; constructors use the containing type name.

Overloads can share an identity. Path plus the 1-based inclusive range makes a
finding unambiguous without requiring compiler symbol resolution.

The callable range begins at its first attached decorator, annotation, or
attribute; otherwise it begins at the declaration. It ends at the last
syntactic token of the body or expression. Unattached leading comments are not
included. Tree-sitter's zero-based, end-exclusive coordinates are converted to
1-based inclusive line ranges.

### Callable physical LOC

`physical LOC = inclusive end line - inclusive start line + 1`

Every physical line in that range counts: annotations, attributes, decorators,
multi-line signatures, braces, blank lines, comments, and expression bodies.
An outer callable's range includes the source occupied by a local function,
while that local function is also measured independently. This is source extent,
not canonical file-LOC semantics.

### Structural nesting depth

Depth starts at zero and is the maximum number of simultaneously active,
meaningful control-flow regions. An `if` chain, loop, switch/when/match, or
try/catch/finally family adds one region. `else` and `elif`/else-if share their
corresponding `if` level. Case arms share the switch level; labels do not add a
second level. Catch and finally arms share the try level. Plain lexical blocks,
boolean expressions, conditional expressions, comprehensions, safe calls,
Elvis/null-coalescing expressions, and lambdas do not add depth. Nested named
callables reset to zero.

This definition measures how many control regions a reader must track, not
indentation or brace count.

### Cyclomatic complexity

Complexity is `1 + decision increments`. The prototype adds one for each:

- `if` condition and `elif`/else-if condition;
- loop;
- non-default switch/when/match arm (one per arm, not per comma-separated label);
- catch handler;
- conditional/ternary expression;
- short-circuit boolean operator occurrence (`and`, `or`, `&&`, `||`);
- Python comprehension/generator expression as one implicit decision.

The switch node, `else`/default/wildcard arm, `try`, `finally`, safe navigation,
Kotlin Elvis, C# null coalescing, and lambda bodies add zero. These exclusions
are deliberate: value fallback and deferred anonymous code do not normalize
cleanly enough across the four languages. Nested named callable bodies are not
charged to the parent.

## Prototype architecture

```text
source bytes
    -> language adapter backed by one parser
    -> named callable plus syntax facts
    -> callable LOC / nesting / complexity measurements
    -> additive callable-scoped finding
```

The research implementation uses one Tree-sitter parse per file. The current
prototype calculates facts directly inside the adapter to keep the experiment
small. Production should expose immutable `ParsedFile`, `CallableFact`, and
control-flow fact values rather than leaking Tree-sitter nodes to guards. Facts
must retain language-specific categories and decision breakdowns so a common
model does not erase meaningful differences.

Malformed trees are rejected. Silent partial measurements from Tree-sitter's
error recovery would look authoritative but would not be deterministic enough
for a guard.

## Language support

| Capability | Python | Go | Kotlin | C# |
| --- | --- | --- | --- | --- |
| Top-level functions | Yes | Yes | Yes | Not a named language construct |
| Methods | Yes | Yes, receiver-qualified | Yes | Yes |
| Named local functions | Yes | Not supported by Go | Yes | Yes |
| Expression-bodied named callable | Lambda-like one-line body is still a `def` | Not supported | Yes | Yes |
| Constructors | `__init__` is a method | Not distinct syntax | Secondary constructor proven | Constructor proven |
| Attached declaration metadata in range | Decorator wrapper adjustment | N/A | Annotation included | Attribute included |
| Stable 1-based ranges | Yes | Yes | Yes | Yes |
| Callable LOC | Proven | Proven | Proven | Proven |
| Structural nesting | Proven | Proven | Proven | Proven |
| Complexity | Proven, with comprehension/match rules | Proven, including type switch | Proven, including `when` | Proven, including switch expressions |

Lambdas are intentionally opaque. This avoids unstable identities and avoids
charging deferred code to an enclosing callable, but it leaves anonymous
control flow unmeasured. Lambda policy is a separate production decision.

## Fixture results

Eight fixture files contain 39 measured callables. Every row below is asserted
by `tests/test_analyzer_feasibility.py`; values are `LOC / depth / complexity`.

| Language | Simple | Long linear | Deep nested | Wide branching | Metadata/comments | Language-specific evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Python | 2 / 0 / 1 | 8 / 0 / 1 | 8 / 4 / 5 | 10 / 1 / 5 | 8 / 0 / 1 | comprehension + ternary + booleans = 4; match/catch = 4 |
| Go | 3 / 0 / 1 | 9 / 0 / 1 | 13 / 4 / 5 | 8 / 1 / 5 | 8 / 0 / 1 | booleans = 3; type switch = 3 |
| Kotlin | 1 / 0 / 1 | 9 / 0 / 1 | 14 / 4 / 5 | 8 / 1 / 5 | 9 / 0 / 1 | `when` = 3; lambda/Elvis/safe-call excluded |
| C# | 1 / 0 / 1 | 10 / 0 / 1 | 19 / 4 / 5 | 9 / 1 / 5 | 9 / 0 / 1 | ternary + booleans = 4; switch expression = 3 |

The long-linear and branching fixtures demonstrate that callable size is not a
complexity proxy. Deep and wide fixtures both reach complexity 5 while their
depths are 4 and 1, demonstrating that complexity is not a nesting proxy.
Comments, strings, and identifiers are never keyword-counted.

Local-function fixtures prove overlapping physical ranges and reset control
metrics in Python, Kotlin, and C#. Go has no named local-function declaration.

## Provider comparison

| Provider | Evidence | Strengths | Costs/limits | Production conclusion |
| --- | --- | --- | --- | --- |
| Tree-sitter | Implemented for all four languages with pinned Python packages and exact fixture assertions | One in-process parse, concrete ranges, broad grammar coverage, no target-language toolchain | Native wheels and grammar ABI must be pinned; node taxonomies differ; syntactic identities only; error recovery must be rejected | Recommended initial provider behind adapters |
| Python `ast` | Compared against Python fixtures | Standard library, semantic node categories, stable end positions | Python only; decorator start requires explicit adjustment; no comments in AST | Useful oracle for the Python adapter, not a universal layer |
| Go `go/parser` / `go/ast` | Go 1.25.4 tooling was available and source ranges are compiler-native | Authoritative Go syntax and positions | Requires Go at runtime or helper binaries for every OS/architecture | Useful oracle or optional Go backend |
| Roslyn | .NET 8/10 SDKs were present; packaging/runtime path assessed | Authoritative C# syntax, symbols available when needed | Requires .NET plus a maintained helper/package graph; much heavier than syntactic guards | Oracle or future backend if syntax-only identity proves insufficient |
| Kotlin compiler/PSI | Runtime feasibility assessed; Java 11 was present but `kotlinc` was absent | Authoritative Kotlin model | Largest/version-sensitive dependency, compiler/JVM distribution burden | Not a universal baseline; possible future Kotlin backend |
| Regex, indentation, or brace counting | Rejected against fixture constructs | Minimal dependency | Fails metadata/signatures, else-if normalization, expressions, comprehensions, switches, and comments/strings | Not suitable |

The prototype dependency is `tree-sitter==0.26.0` plus
`tree-sitter-language-pack==1.14.3`, recorded in `research/requirements.txt`.
On the tested Windows CPython 3.14 environment the language pack installed as a
2.1 MB wheel. It is a research dependency, not a shipped Code Guard dependency.
Production should evaluate individually pinned grammar wheels, verify exact
Windows/Linux/macOS wheel coverage in CI, and fail clearly when an analyzer is
unavailable rather than falling back to text heuristics.

## Result-model compatibility

`CallableFinding` is an additive generic result shape with path, callable,
inclusive range, measured value, state, optional threshold, and optional detail
breakdown. `GuardResult` already supplies the guard id and required policy id.
The JSON compatibility test serializes the issue's nesting example. LOC keeps
its existing `Finding` shape and semantics unchanged.

## Performance sanity

Observed on Windows, Python 3.14.2, Tree-sitter 0.26.0, language-pack 1.14.3:

- research module import: 119 ms;
- first parse/measurement of all eight fixture files: 87 ms;
- 800 warm file parses: 914 ms, approximately 1.14 ms/file.

These are sanity observations, not a benchmark. Parser initialization dominates
the tiny corpus, while warm per-file cost is reasonable for post-edit workflows.
Production should cache parser instances and separately track cold start and
large-file behavior.

## Known limitations

- Identities are lexical and do not resolve aliases, partial types, or overloads.
- Lambdas are opaque; anonymous code is not measured.
- Tree-sitter grammar upgrades may rename nodes or alter ranges.
- Incomplete files are rejected rather than partially analyzed.
- Python comprehensions have no direct cross-language equivalent.
- Elvis and null-coalescing could reasonably be classified as decisions; this
  prototype excludes both pending product evidence.
- The fixtures prove deterministic normalization, not useful universal review
  points across real repositories.
- Java and JavaScript/TypeScript remain follow-up probes.

## Threshold conclusions

- Callable physical LOC: **Outcome B** — useful with project configuration, but
  eight controlled fixtures do not justify a universal REVIEW default.
- Structural nesting: **Outcome B** — the cross-language definition is stable,
  but no universal REVIEW value is justified without representative projects.
- Cyclomatic complexity: **Outcome C** — the common core is useful, but
  comprehensions and fallback/expression constructs require language-specific
  interpretation before thresholds can be compared responsibly.

No production REVIEW or FAIL threshold is introduced.

## Recommendation and next slices

Adopt a small language-adapter boundary with Tree-sitter as the initial pinned
syntax provider, parsing each file once and returning named callables plus
normalized, inspectable control-flow facts. Keep the boundary provider-neutral
so a native oracle/backend can replace one language without changing guards.
Do not build a generic plugin framework.

Small follow-up issues should be:

1. productionize the adapter/fact contract, parser packaging matrix, syntax
   error behavior, and Python/Go oracle parity without enabling guards;
2. implement configurable callable physical LOC as PASS/REVIEW with no default;
3. implement configurable structural nesting as PASS/REVIEW with no default;
4. expand complexity fixtures and real-project sampling to settle the
   comprehension/Elvis/null-coalescing policy before implementing the guard;
5. evaluate lambda treatment and Java/JavaScript/TypeScript coverage separately.
