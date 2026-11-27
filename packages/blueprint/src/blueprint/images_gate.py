"""The `images` gate step, rendered when a Dockerfile or a compose file is tracked (`blueprint gate render`).

a2kay wrote it by hand: hadolint, dockerfmt and BuildKit's `docker build --check` over the Dockerfiles; dclint, yamlfmt and Compose's own
schema check over the compose files. Each tool runs only for the kind of file the repo has;
a missing tool is named (exit 2), never skipped.
The digest-pin check is optional (`[tool.blueprint.gate] image-pins = true`, `image-pin-contexts = ["<build context>"]`): it runs
from the package, `python -m blueprint.recipes.check_dockerfile_pins`, so a repo copies no script. The same option makes every
compose `image:` carry a digest too (`python -m blueprint.compose_pins`, one process over every tracked compose file;
`image-pin-exempt = ["<image prefix>"]` excuses an image built from the same commit).
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from blueprint import gate_py
from blueprint.profile import detect_stacks

if TYPE_CHECKING:
    from pathlib import Path

STEP = "images"
_DOCKERFILES = "'*Dockerfile' '*Dockerfile.*' '*Containerfile'"
_COMPOSES = "'*compose*.yml' '*compose*.yaml'"
_HEADER = (
    "# Rendered by `blueprint gate render` -- never edit; a recipe of the same name in the repo's justfile replaces it\n"
    "# only through a declared override (gate.recipe-shadowing).\n"
)


def render(repo: Path) -> str | None:
    """The part's text, or None when the repo tracks neither a Dockerfile nor a compose file."""
    stacks = detect_stacks(repo)
    dockerfiles, composes = "dockerfile" in stacks, "compose" in stacks
    if not (dockerfiles or composes):
        return None
    tools = [*(("hadolint", "dockerfmt", "docker") if dockerfiles else ()), *(("dclint", "yamlfmt", "docker") if composes else ())]
    lines = [
        f"for t in {' '.join(dict.fromkeys(tools))}; do",
        '    command -v "$t" >/dev/null || { echo "images: $t is not installed -- run just tools" >&2; exit 2; }',
        "done",
        "rc=0",
    ]
    if dockerfiles:
        lines += _dockerfile_lines(repo)
    if composes:
        lines += _compose_lines(repo)
    lines.append('exit "$rc"')
    body = "\n".join(f"    {line}" for line in lines)
    kinds = " and ".join(
        kind
        for kind, present in (
            ("Dockerfiles (hadolint, dockerfmt, BuildKit's `docker build --check`)", dockerfiles),
            ("compose files (dclint, yamlfmt, Compose's schema check)", composes),
        )
        if present
    )
    return f"""{_HEADER}# Image files: {kinds}.
# `docker build --check` parses and lints the Dockerfile with BuildKit and runs no layer; a failing RUN is the image build's.
[group('gate')]
images:
    #!/usr/bin/env bash
    set -euo pipefail
{body}
"""


def _dockerfile_lines(repo: Path) -> list[str]:
    files = f"git ls-files -z {_DOCKERFILES} | {{ grep -zv '\\.dockerignore$' || true; }}"
    gate = gate_py.settings(repo).get("gate", {})
    lines = []
    if isinstance(gate, dict) and gate.get("image-pins") is True:
        contexts = gate.get("image-pin-contexts", [])
        flags = "".join(f" --context {shlex.quote(str(c))}" for c in contexts) if isinstance(contexts, list) else ""
        lines.append(f"uv run python -I -m blueprint.recipes.check_dockerfile_pins{flags} || rc=1")
    lines += [
        f"{files} | xargs -0 -r hadolint || rc=1",
        f"{files} | xargs -0 -r -n1 dockerfmt --check -n || rc=1",
        f'while IFS= read -r -d "" f; do docker build --check -f "$f" "$(dirname "$f")" || rc=1; done < <({files})',
    ]
    return lines


def _compose_lines(repo: Path) -> list[str]:
    files = f"git ls-files -z {_COMPOSES}"
    gate = gate_py.settings(repo).get("gate", {})
    pins = []
    if isinstance(gate, dict) and gate.get("image-pins") is True:
        exempt = gate.get("image-pin-exempt", [])
        flags = "".join(f" --exempt {shlex.quote(str(e))}" for e in exempt) if isinstance(exempt, list) else ""
        pins.append(f"uv run python -I -m blueprint.compose_pins{flags} || rc=1")
    return [
        *pins,
        f"{files} | xargs -0 -r dclint --max-warnings 0 || rc=1",
        f"{files} | xargs -0 -r yamlfmt -lint || rc=1",
        'compose() { if command -v docker-compose >/dev/null; then docker-compose "$@"; else docker compose "$@"; fi; }',
        f'while IFS= read -r -d "" f; do compose -f "$f" config --no-interpolate -q || rc=1; done < <({files})',
    ]
