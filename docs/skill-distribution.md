# Code Guard skill distribution

The `agent-code-guard` Python distribution is the single versioned release
unit. It contains the `code-guard` CLI, runtime, and an inert,
version-matched skill payload. Keep their lifecycle steps distinct:

1. Install the Python distribution with pipx, pip, or uv.
2. Invoke the installed `code-guard` CLI.
3. Locate the bundled skill:

   ```bash
   code-guard --skill-path
   ```

4. If the agent platform needs a copied payload, optionally export it:

   ```bash
   code-guard --export-skill <target-directory>
   ```

5. Let the agent platform discover or activate that directory through its own
   supported mechanism.

pipx installs and isolates the command; it does not register the skill with
every agent platform. Agent Code Guard does not know a universal skill
directory or activation API. Platform activation is separate, and exporting
into a persistent skill directory or changing platform configuration requires
user authorization.

CLI-only use needs no skill export. For example,
`code-guard . --changed-only` runs independently of whether a platform has
activated the bundled skill. The skill does not affect startup, scope,
configuration, parser loading, findings, or exits.

## Discovery and export guarantees

`--skill-path` prints the absolute path of the active installed
distribution's canonical payload without project discovery, configuration
loading, Git work, or guard execution.

`--export-skill` copies into exactly the supplied directory. The target must
be missing or empty; export rejects a non-empty target and never overwrites it.
The export contains `SKILL.md`, `LICENSE.txt`, `agents/openai.yaml`, the
policy files under `references/`, and a generated
`.agent-code-guard-version` marker recording the producing distribution
identity. After upgrading Agent Code Guard, refresh any exported snapshot so
the platform uses the newly installed version-matched skill.

The checkout compatibility runner at
`skills/code-guard/scripts/code_guard.py` is for repository and skill
compatibility development. It is excluded from installed skill payloads and is
not a normal installation or execution path.

For read-only troubleshooting, `code-guard doctor` or
`code-guard doctor --json` validates the bundled payload along with the active
runtime and providers. It does not export or activate a skill. See the
[human and agent workflow](agent-workflow.md) for execution cadence rather than
duplicating it here.
