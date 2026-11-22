# Rendered by `blueprint gate render` -- never edit; a recipe of the same name in the repo's justfile replaces it only through a declared override (gate.recipe-shadowing).
# The shell stack: every tracked shell script passes shellcheck (pinned in mise.toml), at its default severity.

[group('gate')]
scripts scope="changed":
    #!/usr/bin/env bash
    set -euo pipefail
    command -v shellcheck >/dev/null || { echo "scripts: shellcheck is not installed -- run just tools" >&2; exit 2; }
    list=$(mktemp); trap 'rm -f "$list"' EXIT
    uv run python -m any_gate changed --scope {{ scope }} --config .shellcheckrc '*.sh' > "$list"
    [ -s "$list" ] || { echo "skipped scripts: no shell script changed"; exit 0; }
    xargs -0 shellcheck < "$list"

# The release gate's form of `scripts`: every tracked shell script, not only the changed ones.
[group('gate')]
scripts-all: (scripts "all")
