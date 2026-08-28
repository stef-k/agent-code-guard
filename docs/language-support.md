# Language support

Syntax guards use deterministic parser-backed facts for applicable files.
Unsupported artifacts are left inapplicable rather than analyzed heuristically.

## Syntax languages and extensions

| Language | Extensions or regions |
| --- | --- |
| Python | `.py` |
| Go | `.go` |
| Kotlin | `.kt`, `.kts` |
| C# | `.cs` |
| Java | `.java` |
| JavaScript | `.js`, `.jsx` |
| TypeScript | `.ts`, `.tsx` |
| Vue | JavaScript or TypeScript `<script>` regions in `.vue` |
| C++ | `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, `.hxx` |
| Rust | `.rs` |
| PHP | `.php` |
| Swift | `.swift` |
| Dart | `.dart` |

Generic `.h` is deliberately not syntax-dispatched because the extension does
not establish C versus C++ language context.

## Mixed-content files

For Vue single-file components, syntax guards analyze inline JavaScript or
TypeScript script regions. Vue template and style regions are not executable
syntax input. External `src` scripts and unsupported explicit script languages
are fail-closed tool errors rather than silently ignored inputs.

For PHP, parser-backed analysis uses one identity-mapped whole-file region, so
facts retain their original positions in mixed-content files. The grammar's
surrounding non-PHP markup emits no executable facts.

## C# contextual keywords

The upstream C# Tree-sitter grammar does not currently parse every valid use of
`async` as a contextual identifier. When—and only when—the first C# parse has
errors, Code Guard can retry once after replacing parser-problem `async` tokens
used as expression identifiers or named-argument names with an equal-length
neutral identifier. The corrected tree is accepted only when it is error-free
and every replacement has the expected structural role; facts still use the
original source bytes, paths, and coordinates.

Unknown or ambiguous parser problems, missing or remaining syntax, and `async`
in any other problematic role continue to fail closed with tool exit `3`.
Already-valid C#, including genuine `async` modifiers and `await` expressions,
uses the unchanged single parse.

## Markdown

Markdown document-size and direct-section-size guards apply to `.md` files.
The `.markdown` extension is not currently enabled. Markdown is measured as a
documentation format, independently of syntax-language dispatch.

## Failure behavior

Malformed applicable syntax and failures to load a required parser provider or
grammar are fail-closed tool errors (exit `3`). Code Guard does not produce a
partial heuristic result. Files with unsupported extensions are simply
inapplicable to syntax or Markdown guards; other applicable guards may still
consider them according to their own configured extension policy.

Operating-system, architecture, Python-version, and native-wheel availability
are documented separately in [Platform support](platform-support.md).
