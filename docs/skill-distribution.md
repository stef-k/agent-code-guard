# Code Guard skill distribution

The `agent-code-guard` Python distribution is the single versioned release
unit. A pip, pipx, or uv tool installation receives the `code-guard` command,
its runtime, and an inert canonical Code Guard skill payload from the same
artifact version. Installation does not inspect or modify any agent directory
or configuration. Installing `agent-code-guard` through pip, pipx, or uv
provides the command, runtime, and exact version-matched skill payload.

CLI-only use is fully supported. Install the Python distribution and run, for
example, `code-guard . --changed-only`. The bundled skill does not affect
startup, scope, configuration, parser loading, findings, or exit behavior, and
it never needs to be exported for CLI-only use.

For skill-and-CLI use:

1. Install the Python distribution by the normal pip, pipx, or uv tool flow.
2. Run `code-guard --skill-path` to print the absolute path of that installed
   distribution's exact skill payload, or run
   `code-guard --export-skill <target-directory>` to copy it into exactly the
   supplied directory.
3. Register or install that directory using the chosen agent system's own
   mechanism. Agent-specific destinations and configuration are outside Code
   Guard's responsibility.
4. The skill invokes the installed `code-guard` command.

`--skill-path` performs no project discovery, configuration loading, Git work,
or guard execution. `--export-skill` has the same isolation, creates a missing
target, and rejects an existing non-empty target instead of overwriting it. It
copies only `SKILL.md`, `LICENSE.txt`, `agents/openai.yaml`, and the policy files
under `references/`; the checkout-only `scripts/code_guard.py` compatibility
runner is deliberately excluded.

Direct `--skill-path` use is intrinsically version-coupled to the installed
Python distribution. An export is a snapshot and contains a generated
`.agent-code-guard-version` marker with the producing distribution version.
After upgrading Agent Code Guard, callers must replace or re-export their
agent-installed snapshot. Code Guard performs no background or automatic agent
updates.
