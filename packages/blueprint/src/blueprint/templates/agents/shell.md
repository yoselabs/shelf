# Shell conventions

Stack: shell (sh and bash scripts). The gate is `just check`; this file is what to know before writing or changing a script.

## Tools per role

| role | tool | configured in |
|---|---|---|
| formatter | shfmt `-d` | `.editorconfig` `[*.sh]` |
| linter | shellcheck at its default severity (never `-S error`: it misses unquoted expansions) | inline `# shellcheck disable=SCnnnn` with a reason |
| strict mode | every executable script: `set -euo pipefail` (bash) or `set -eu` (/bin/sh) | the script's header |
| tests | none proven yet: bats-core is the candidate | - |
| hooks | prek: shellcheck and shfmt on staged scripts | [gate.md](gate.md) |

Both tools are pinned in `mise.toml`.

## Rules

| rule | why |
|---|---|
| `set -euo pipefail` on the line after the header comment | A failed command, an unset variable or a failed pipe stops the script, not the next step |
| A script that must run on after a failure (a probe, a report) keeps `-u` and `pipefail` and says `# strict: no -e, <reason>` | The engine accepts the waiver only with a reason |
| Quote every expansion: `"$var"`, `"$@"`; `rm -rf "${dir:?}"/*` | Word splitting and an empty variable turn a delete into `rm -rf /*` |
| A library meant to be sourced is not executable (mode 644) and sets no modes | The caller owns the modes |
| `#!/usr/bin/env bash` for bash; bash 4+ features only if the header says so | macOS ships bash 3.2 |
| A script past one screen of logic moves to the repo's main language | Shell has no types or tests worth the name; the main language has both |
| Each shellcheck disable is inline, on the line, with why | A file-wide disable hides the next real finding |

## Run

```bash
just check                              # the gate
shfmt -w $(git ls-files '*.sh')         # format in place
```
