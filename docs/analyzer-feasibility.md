# Callable Analyzer Feasibility

This report records issue #4's two-phase research prototype. It is evidence for
a later production design, not an enabled Code Guard feature. Canonical file LOC
and its policy are unchanged.

## Evidence phases and final conclusion

Phase A established exact measurements for Python, Go, Kotlin, and C#. It
provisionally recommended provider-neutral language adapters backed by one
Tree-sitter parse per file, range-based callable LOC, meaningful control-flow
nesting, and documented decision counting.

Phase B added Java, JavaScript, TypeScript, JSX, TSX, and Vue SFC script regions.
It tested the two assumptions most likely to fail: modern JS/TS function-like
syntax and files containing more than one language.

The final conclusion is that the Phase A provider recommendation **survived with
modifications**:

```text
source file
    -> source/container adapter
    -> one or more executable regions
       { original path, embedded language, bytes, original offset mapping }
    -> provider-neutral language adapter
    -> named callable and control-flow facts
    -> callable LOC / nesting / complexity
```

Ordinary files yield one identity-mapped executable region. Vue uses one
container parse followed by one embedded parse per script region. The three
metrics share each executable parse. Grammar nodes remain private to adapters.
This is a small region boundary, not a generic plugin framework.

Tree-sitter remains the recommended initial pinned provider after the expanded
corpus. Java and all JS-family grammars produced stable syntax/ranges without
requiring target-language toolchains. Vue proves that `suffix -> language`
cannot be the top-level architecture: container extraction must precede language
parsing. Native parsers remain useful oracles and possible per-language backends.

## Final callable model

The common rule includes named top-level functions, named methods, constructors,
and named local functions where supported. Named expression-bodied declarations
are included. Identities are lexical rather than symbol-resolved and are always
paired with original path and a 1-based inclusive source range.

Language-appropriate identities include:

- Python: `module.Type.method` or `module.outer.local`;
- Go: `package.function` or `package.Receiver.method`;
- Kotlin/Java: `package.Type.method` and `package.Type.Type` for constructors;
- C#: `Namespace.Type.Method`, with the containing type repeated for constructors;
- JS family: `file.Type.method`, `file.object.method`, or `file.outer.local`.

Overloads can share an identity; path plus range disambiguates them.

### JS/TS functions, arrows, and callbacks

JS/TS/JSX/TSX include executable `function` declarations, class methods and
constructors, object shorthand methods, variable-assigned arrows, and
variable-assigned function expressions. TypeScript method signatures, function
types, interfaces, and other bodyless declarations are excluded.

A function expression or arrow assigned to a simple lexical variable receives
that target's name. Its measurement range starts at the sole lexical declaration
(`const`/`let`/`var`) and ends at the callable body or expression token; the
trailing semicolon is excluded. This counts the readable ownership syntax in:

```javascript
const calculate =
    (value) => {
        return value;
    };
```

Named local arrows and function expressions nest under their enclosing callable.
React arrow components are ordinary lexical callables; there is no React rule.

Truly anonymous JS-family callbacks are first-class callables. Their identity is
the enclosing callable plus original 1-based source coordinates, for example
`owner.<callback@46:30>`. This is deterministic and directly locatable without
depending on AST traversal order. Callback control flow is measured independently
and is not charged to the parent. Coordinates shift when preceding source moves,
as finding ranges already do, but the policy avoids major unmeasured complexity
blind spots in callback-heavy applications.

Kotlin, C#, Go, Java, and expression-only Python lambdas now use the same
coordinate-owned callback boundary. Their controls and decisions belong to the
child `CallableKey`, are not charged to the owner, and reset nesting.

## Measurement definitions

### Callable physical LOC

`physical LOC = inclusive end line - inclusive start line + 1`

The range begins at the first attached decorator, annotation, or attribute;
otherwise it begins at the declaration or stable lexical assignment owner. It
ends at the final syntactic token of the body or expression. Signature lines,
braces, JSX, comments, blank lines, and named nested declarations inside the
range count. An outer callable's physical range can overlap a local callable,
while its control metrics exclude that nested callable.

Phase B supports this Phase A definition with one qualification: stable JS/TS
assignment ownership is part of the callable start. Vue uses the mapped original
container range, never temporary extracted-script coordinates.

### Structural nesting depth

Depth starts at zero and is the maximum number of simultaneously active,
meaningful executable control-flow regions. An `if` chain, loop,
switch/when/match, or try/catch/finally family adds one region. Else and else-if
share the if level. Case arms share the switch level; catch/finally arms share
the try level. Plain lexical blocks, resource/synchronization scopes, boolean or
conditional expressions, comprehensions, safe calls, nullish/fallback operators,
and function boundaries do not add depth. Nested callables reset at zero.

JSX element hierarchy and Vue template hierarchy add no executable nesting.
Phase B therefore supports the Phase A nesting definition unchanged.

### Cyclomatic complexity

Complexity is `1 + decision increments`. The prototype adds one for each:

- `if` and else-if condition;
- loop;
- non-default/non-wildcard switch/when/match executable arm;
- catch handler;
- conditional/ternary expression;
- short-circuit `and`/`or` or `&&`/`||` operator occurrence;
- Python comprehension/generator expression as one implicit decision.

Grouped labels leading to one executable arm count once. Switch nodes, default
or wildcard arms, `try`, `finally`, optional navigation, Kotlin Elvis, C# null
coalescing, and JS/TS nullish coalescing add zero. In JSX, `{enabled && ...}` and
ternaries are ordinary executable decisions; markup nodes are not decisions.

Phase B strengthens Outcome C: the common decision core is useful, but Python
comprehensions, fallback operators, switch grammars, and callable boundaries
still require language-specific interpretation.

## Support table

| Capability | Python | Go | Kotlin | C# | Java | JS | TS | JSX | TSX | Vue SFC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Named declarations/methods | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Delegated |
| Constructors | Method convention | N/A | Yes | Yes | Yes | Yes | Yes | N/A | N/A | Delegated |
| Named local callable | Yes | N/A | Yes | Yes | Lambda opaque | Yes | Yes | Yes | Yes | Delegated |
| Lexically assigned arrow/function | N/A | N/A | N/A | N/A | Lambda opaque | Yes | Yes | Yes | Yes | Delegated |
| Anonymous callback finding | No | N/A | No | No | No | Coordinate identity | Coordinate identity | Coordinate identity | Coordinate identity | Delegated |
| Attached metadata in range | Decorator | N/A | Annotation | Attribute | Annotation | N/A | Decorator | N/A | Supported by TSX grammar | Delegated |
| Bodyless declaration excluded | N/A | N/A | N/A | N/A | Yes | Yes | Yes | Yes | Yes | Delegated |
| Original stable range | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes, remapped |
| LOC/depth/complexity | Proven | Proven | Proven | Proven | Proven | Proven | Proven | Proven | Proven | Proven for scripts |

Vue is a container, not an embedded language. Each finding retains JavaScript or
TypeScript as its embedded language.

## Phase B results

Eighteen fixture files now assert exact identity, original 1-based inclusive
range, physical LOC, nesting, and complexity for 96 callables across both phases.

### Java

Methods, constructors, annotations, multi-line signatures, long linear code,
four-level nesting, wide branching, else-if, enhanced loops, two catches,
ternary/boolean decisions, classic switch groups, and switch-expression rules
are measured. Constructor identity is `package.Type.Type`; the annotation is in
the constructor range. Both switch forms produce depth 1 and complexity 3 for
two non-default executable arms. Java lambdas are independently measured and
reset/exclude their body from the owner.

### JavaScript

Function declarations, class constructors/methods, object methods,
variable-assigned arrows/function expressions, and named local expressions have
stable lexical identities. Deep/wide flow, else-if, loops, catch, switch,
ternary, and short-circuit expressions are measured. Optional chaining and `??`
are deliberately excluded. Map/Promise callbacks receive independent
source-coordinate identities, preventing parent double counting or blind spots.

### TypeScript

Type annotations, generic functions/methods, optional parameters, decorators,
arrows, and function expressions preserve callable ranges and measurements.
Interface methods and function types produce no findings. Optional chaining and
nullish coalescing do not increment complexity; ordinary if/boolean/ternary
syntax does.

### JSX and TSX / React syntax

Declaration and arrow components are ordinary JS-family callables. JSX
short-circuit rendering and ternaries count as normal expressions. Nested
`div/section/article` markup remains depth 0. Event and map callbacks receive
independent coordinate identities. React-specific framework policy is absent.

### Vue SFC

The Vue container parser locates `script_element` regions and ignores template
and style elements. Missing `lang`, `js`, and `javascript` delegate to JavaScript;
`ts` and `typescript` delegate to TypeScript. Other language values are rejected
rather than silently parsed as JavaScript. Script attributes are validated before
empty content is skipped, so an empty external `src` region still errors.
`setup` affects component semantics, not parser selection.

Each executable region stores original path, embedded language, exact raw bytes,
and its starting byte offset. Parser points map through the original UTF-8 bytes,
so same-line tags, non-ASCII prefixes, multiple script blocks, and original line
numbers remain representable. Exact tests prove `Options.vue` reports its
callable at lines 8–13 and `Setup.vue` reports TypeScript callables at 8–13 and
17–19 rather than extracted coordinates. Malformed container or embedded syntax
is rejected. External `src` scripts are explicitly unsupported by this prototype.

No template or style metrics are implemented; those belong to issue #6.

## Parser/provider comparison

| Provider | Phase B evidence | Strengths | Costs/limits | Conclusion |
| --- | --- | --- | --- | --- |
| Tree-sitter | Implemented for ten languages/formats with pinned packages and exact fixtures | One executable parse feeds all metrics; concrete byte/point ranges; Java, JS, TS, JSX, TSX and Vue grammars available | Grammar taxonomy differs; ABI/versions and native wheels must be pinned; tolerant errors must be rejected | Recommended initial provider behind region/language adapters |
| Python `ast` | Retained decorator/range oracle test | Standard library and authoritative Python categories | Python only; decorators need start adjustment | Python oracle |
| Go `go/parser` | Go fixtures compile with Go 1.25.4; native position API assessed | Authoritative Go syntax | Go runtime or helper binaries | Go oracle/optional backend |
| Java compiler | Java 11 available; ordinary Java fixture compilation used where supported | Authoritative Java syntax | Local Java 11 cannot validate modern switch expressions; runtime/helper burden | Oracle, not universal runtime |
| JS/TS compiler ecosystems | Node 22 available; runtime/package implications assessed | Authoritative JS and TS semantics | Multiple parser modes/package graph; Vue still needs container extraction | Useful oracles, not required prototype dependencies |
| Roslyn / Kotlin PSI | Phase A environment/runtime assessment | Authoritative native models | Heavy/version-sensitive toolchains | Possible per-language backends |
| Regex/brace/indentation | Rejected by metadata, callbacks, JSX, switches, and Vue regions | Minimal dependency | Incorrect ranges and decision boundaries | Not suitable |

The research dependency remains `tree-sitter==0.26.0` and
`tree-sitter-language-pack==1.14.3`. The broad language pack is convenient for
research, not an automatic production dependency choice. Production packaging
must test individually pinned grammar wheels and exact Windows/Linux/macOS
coverage, cache parsers, and fail clearly rather than fall back to text counting.

## Result-model compatibility

`CallableFinding` remains additive and leaves LOC's `Finding` untouched. It can
carry original path, callable, inclusive range, measured value, state, threshold
metadata, detail breakdown, and optional embedded language. A Vue compatibility
test serializes `src/Foo.vue`, original lines 21–35, and `typescript`.
`GuardResult` continues to provide guard and required-policy identity.

## Performance sanity

Recordings use Windows, Python 3.14.2, Tree-sitter 0.26.0, and language-pack
1.14.3. These are workflow sanity observations, not benchmarks. Phase B records
cold import at 45 ms, first analysis of 18 files/96 callables at 104 ms, 1,800
warm file analyses at 1,520 ms (about 0.84 ms/file), and 200 warm Vue
container-plus-region analyses at 59 ms (about 0.30 ms/file). Production should
cache parsers and retain separate container/executable parse telemetry.

## Threshold conclusions after Phase B

- Callable physical LOC: **Outcome B survived with qualification** — a
  configurable REVIEW point is useful, but lexical assignment/container ranges
  expand the definition and no universal default is justified.
- Structural nesting: **Outcome B survived unchanged** — normalization remains
  stable across executable languages and ignores markup hierarchy, but fixture
  evidence does not establish a universal REVIEW value.
- Cyclomatic complexity: **Outcome C survived and strengthened** — a shared core
  exists, while comprehensions, fallback operators, switch forms, JSX expression
  usage, and callback boundaries require language-specific interpretation.

No production REVIEW or FAIL threshold is introduced.

## Known limitations

- Identities are lexical and do not resolve overloads, aliases, or dynamic
  property assignments; path and range remain the authoritative locator.
- Anonymous JS-family callback identities shift with their source coordinates.
- Python lambdas are expression-only; statement controls cannot occur in them.
- Simple variable assignment is proven; destructuring, computed property targets,
  assignment expressions, and class-field arrows need separate evidence.
- Vue external scripts are unsupported, and the container grammar does not
  validate embedded syntax; each region is validated separately.
- Tree-sitter grammar upgrades can change taxonomy or ranges.
- Syntax trees containing errors are rejected rather than partially measured.
- The corpus proves deterministic normalization, not universal threshold value.

## Production second-wave validation (#8)

The shipped pipeline was subsequently validated without a second parser or fact
model across C++, Rust, PHP, Swift, and Dart using Tree-sitter 0.26.0 and
tree-sitter-language-pack 1.14.3. Each fixture asserts lexical identity,
original range, inclusive physical LOC, structural nesting, and complexity
derived only from immutable `AnalysisFacts`.

| Language | Callable and closure policy | Control/decision mapping | Provider result and limitations |
| --- | --- | --- | --- |
| C++ | Free functions, methods, constructors, destructors, operators, templates, and nested-class methods are named. Assigned lambdas use the declaration target; callbacks use source coordinates. | Conditions, loops, switch, try/catch, ternary, and short-circuit operators map directly. Preprocessor directives add no runtime decisions. | `.cpp/.cc/.cxx/.hpp/.hh/.hxx` parse deterministically. `.h` remains excluded. `#define`, `#ifdef`, and `#if` structure is lexical potential code: no macro expansion, configuration selection, or claim that a reported callable is compiled. Error nodes reject the whole file; a future specialized backend is not justified by this evidence. |
| Rust | Free, trait-default, and impl functions are named. Bound closures use the binding; callbacks use coordinates. | `if let` is a condition and `while let` a loop; patterns add zero. Non-wildcard `match` arms count, explicit guards add `pattern_guard`, and expression-oriented controls use the same facts. | The grammar exposes stable ranges and distinct pattern/guard nodes. No Rust toolchain is required. |
| PHP | Functions, methods, constructors, bound arrows/closures, and anonymous callbacks are independent callables. | `if/elseif`, loops, switch/match arms, catches, ternary, and short-circuit booleans count. `??` remains a non-decision fallback. | One whole-file PHP region preserves original `.php` bytes/path across multiple PHP islands; HTML `text` nodes emit no executable facts. This avoids breaking valid PHP spanning tags and requires one executable parse. |
| Swift | Functions, methods, initializers, extension/protocol executable defaults, bound closures, and callbacks are represented. | `guard` is a condition: only its failure body nests. Loops/switch/do-catch map normally; non-default patterns and `where` guards count. Optional syntax alone does not. | Stable lexical ranges are available. Protocol bodies require a small adapter join for the grammar's adjacent declaration/body shape; the common facts remain unchanged. |
| Dart | Top-level, async, method, constructor, local functions, bound closures, and callbacks are represented. | Conditions, loops, switch cases, catches, ternary, and short-circuit booleans count. Null-aware access and `??` do not. | Stable ranges are available. A small adapter joins the grammar's adjacent signature/body nodes and preserves one parse/fact pass; Flutter semantics are out of scope. |

The architecture **survived with small, evidence-driven adapter extensions**.
No `AnalysisFacts` field changed. Callable LOC strengthens Outcome B while
qualifying declaration ownership for templates and closures. Structural nesting
strengthens Outcome B because patterns, markup, preprocessing, and callable
boundaries remain distinct from executable control depth. Complexity strengthens
but further qualifies Outcome C: the common core remains useful, while guarded
patterns and fallback/optional constructs need explicit language mapping. No
universal threshold or production syntax guard was introduced.

## Recommended production slices

1. Productionize source/container regions, byte mapping, language adapter/fact
   contracts, parser caching, syntax errors, and cross-platform grammar packaging
   without enabling guards.
2. Harden JS-family lexical targets (object properties, class fields, assignment
   expressions) and callback identity/details behind the adapter contract.
3. Add configurable callable physical LOC as PASS/REVIEW with no default.
4. Add configurable structural nesting as PASS/REVIEW with no default.
5. Expand real-project complexity sampling and settle fallback/comprehension and
   Java/JS-family lambda policy before enabling complexity.
6. Keep template/style and other structured-artifact guard research in issue #6.
