# Security Policy

## Reporting a vulnerability

Do not report suspected security vulnerabilities through public GitHub issues. Use [GitHub's private vulnerability reporting](https://github.com/stef-k/agent-code-guard/security/advisories/new) instead, and do not post exploit details, credentials, private repository content, access tokens, or other sensitive information publicly.

Use the private route for vulnerabilities that could compromise users, repositories, execution environments, package or release integrity, or other security-sensitive behavior. This policy concerns vulnerabilities in Agent Code Guard or its distribution and workflows; it does not mean Agent Code Guard is a security-analysis product.

Reports will be reviewed as maintainer availability permits.

## Installer certificate trust

The [October 2026 Python advisory](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)
requires pip >=26.2.2 or uv >=0.13.4. Follow the
[installation guide](https://stef-k.github.io/agent-code-guard/usage.html#installation)
before downloading dependencies. Refresh system CA stores too; an installer
version alone does not establish the trust state of a particular host.

CI bootstraps the advisory's exact pip 26.2.2 wheel with a locally pinned
SHA-256, no index, no dependencies, and no cache. This protects the first wheel's
integrity even when the seeded pip still has stale roots. `pip debug` records
the effective interpreter, pip, vendored library versions, and CA overrides.

| Download path | Trust after bootstrap |
| --- | --- |
| Windows, Linux, macOS analysis jobs and Python 3.10–3.14 compatibility jobs | pip 26.2.2: system roots through truststore plus vendored certifi 2026.10.19 |
| Release build tools and isolated build dependencies | Same bootstrapped pip and default combined trust |
| Fresh wheel and sdist smoke environments | Each environment bootstraps independently, then uses the same combined trust |
| pipx pip backend | Separate shared pip; patch that environment before downloads |
| uv and pipx uv backend | uv >=0.13.4; its root-store choice remains installer configuration |

The upstream `pypa/gh-action-pypi-publish` container is a separate trust boundary.
At inspected revision `7245906fb61fa33a13554f9d5fb856fe61758086`, its runtime pins
certifi 2026.10.19, while its image-build prerequisites pin pip 26.2. The host
bootstrap does not retrofit that upstream image's build history. No compromised
chain or exploitation was demonstrated by this investigation.

Agent Code Guard's wheel and sdist do not vendor certifi or a root store. The
runtime dependencies remain `tree-sitter==0.26.0` and
`tree-sitter-language-pack==1.14.3`; this patch changes installer guidance and
CI bootstrap, without changing analyzer behavior.

## Support posture

Until 1.0, security maintenance is best-effort for the current development line and latest available release. Older versions may not receive backports.
