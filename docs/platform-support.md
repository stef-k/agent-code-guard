# Platform support

Agent Code Guard publishes a pure-Python wheel, but normal zero-config syntax
analysis requires the pinned native packages `tree-sitter==0.26.0` and
`tree-sitter-language-pack==1.14.3`. The effective binary-install envelope is
the intersection of compatible wheels from both releases, not every platform
that can run CPython.

## Maintained Python versions

The maintained interpreter range is CPython 3.10–3.14. `requires-python =
">=3.10"` is an installer constraint, not a promise that the complete native
dependency stack has wheels for every CPython-supported platform.

## Normal binary installation

This table describes the normal binary-install envelope established by the
pinned dependency wheel set. It does not mean Agent Code Guard CI directly
tests every listed architecture.

| Platform | Architecture | Native dependency requirement/status |
| --- | --- | --- |
| Windows | x86-64 | Compatible wheels for CPython 3.10–3.14 |
| Windows | ARM64 | Compatible wheels for CPython 3.10–3.14 |
| macOS | x86-64 | Compatible wheels; deployment floor is macOS 10.12 for CPython 3.10–3.11, 10.13 for 3.12–3.13, and 10.15 for 3.14 |
| macOS | ARM64 | Compatible wheels for macOS 11+ and CPython 3.10–3.14 |
| Linux (glibc) | x86-64 | Compatible wheels require glibc 2.34+ |
| Linux (glibc) | ARM64 | Compatible wheels require glibc 2.34+ |

The exact `tree-sitter-language-pack` wheels use `cp310-abi3` with platform
tags `win_amd64`, `win_arm64`, `macosx_10_12_x86_64`,
`macosx_11_0_arm64`, `manylinux_2_34_x86_64`, and
`manylinux_2_34_aarch64`. One ABI3 wheel per platform covers the maintained
Python range. The release also includes an sdist.

`tree-sitter` publishes separate `cp310` through `cp314` wheels. Its Windows
tags cover x86-64 and ARM64; its macOS tags cover x86-64 and ARM64 with the
version-specific deployment floors reflected above. Its Linux wheels are
broader: x86-64 and ARM64 wheels include manylinux 2.17/2.28 tags, x86-64 also
has musllinux 1.2 wheels, and riscv64 has manylinux wheels. It also includes an
sdist. Those additional artifacts do not broaden the intersection because the
pinned language pack is the limiting dependency.

Artifact evidence was read from the machine-readable PyPI release metadata for
the exact pins on 2026-08-24:

- `https://pypi.org/pypi/tree-sitter/0.26.0/json`
- `https://pypi.org/pypi/tree-sitter-language-pack/1.14.3/json`

## Linux libc boundary

The normal Linux binary path is specifically glibc 2.34+ on x86-64 or ARM64;
it is not generic Linux support. On glibc older than 2.34, the pinned language
pack has no compatible prebuilt wheel, so normal binary installation is outside
the release envelope and pip may attempt its sdist instead.

The language pack publishes no musllinux wheel. Alpine Linux and other musl
environments are therefore outside the normal binary-install envelope even
though `tree-sitter` itself publishes musllinux x86-64 wheels.

## Source builds and unsupported binary targets

Source builds are best-effort and not release-supported. The PyPI sdists may
allow pip to attempt a native build on older-glibc Linux, musl/Alpine, Linux
riscv64, 32-bit systems, or other unlisted platform/architecture combinations.
The exact language-pack sdist declares the Maturin build backend and builds a
Rust/PyO3 extension, so an appropriate native compiler, Rust toolchain, and
dependency build tooling may be required. Agent Code Guard does not currently
CI-validate these platform/toolchain combinations, and success is not
guaranteed.

If the complete pinned dependency stack has no compatible wheels for a target,
that target is outside the normal binary-install envelope. Failure to build or
load a required native dependency is an installation or deterministic tool
failure. Code Guard never silently falls back to regex, incomplete syntax
facts, or a passing result.

## CI coverage vs wheel availability

Project CI directly exercises Windows, Ubuntu, and macOS GitHub-hosted runners
on CPython 3.12. Ubuntu CI also exercises CPython 3.10, 3.11, 3.12, 3.13, and
3.14 through normal installation, parser-backed analysis, skill discovery, and
the full test suite. Other entries in the binary envelope are based on upstream
wheel metadata, not direct Agent Code Guard CI on every architecture.

## Updating this contract

Re-evaluate this contract whenever either native dependency pin, the maintained
Python range, or CI runner/platform coverage changes. Exact wheel tags and
current CI evidence are the sources of truth; distribution-name lists are not.
