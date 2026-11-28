"""`layout.root-files-in-config`: tool config files live in `.config/` and caches in `.cache/`, not at the repo root (ADR 0035).

Only what the tool reads from another place when told to is judged (the measurements are in the ADR), and only what the engine reads in the
new place too: a file the repo cannot move never fails the row. The justfile, mise.toml, the hook config, gate-inputs.toml, `.blueprint/`,
package.json and the Dockerfile and compose files are not listed here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Context, Finding, FixedBy, check, failing, passing

if TYPE_CHECKING:
    from collections.abc import Sequence

_ID = "layout.root-files-in-config"
_STATEMENT = "tool config files sit in .config/ and caches in .cache/, not at the repo root (ADR 0035)"

# root name -> where it goes; the rendered recipes pass the flag (hadolint -c, yamlfmt -conf, dclint -c, gitleaks --config).
MOVABLE: dict[str, str] = {
    ".gitleaks.toml": ".config/gitleaks.toml",
    ".hadolint.yaml": ".config/hadolint.yaml",
    ".hadolint.yml": ".config/hadolint.yaml",
    ".yamlfmt.yaml": ".config/yamlfmt.yaml",
    ".yamlfmt": ".config/yamlfmt.yaml",
    ".dclintrc": ".config/dclintrc.json",
    ".dclintrc.json": ".config/dclintrc.json",
    "typos.toml": ".config/typos.toml",
    "_typos.toml": ".config/typos.toml",
    ".typos.toml": ".config/typos.toml",
}

# (table path in pyproject.toml, key, value, config files that mean the tool is configured somewhere else)
_CACHES: tuple[tuple[tuple[str, ...], str, str, tuple[str, ...]], ...] = (
    (("tool", "ruff"), "cache-dir", ".cache/ruff", ("ruff.toml", ".ruff.toml")),
    (("tool", "coverage", "run"), "data_file", ".cache/coverage", (".coveragerc",)),
)


def _table(data: dict[str, object], path: Sequence[str]) -> dict[str, object] | None:
    node: object = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node if isinstance(node, dict) else None


def _in_cache(value: object) -> bool:
    """Whether a cache path points into `.cache/` (from the Python folder, `../.cache/` reaches the repo's)."""
    if not isinstance(value, str):
        return False
    text = value.replace("\\", "/")
    return text.removeprefix("./").startswith(".cache/") or text.startswith("../.cache/")


def _cache_fixes(ctx: Context) -> list[tuple[str, str]]:
    """`(evidence, remedy)` per cache setting a used tool still leaves at the tool default; empty without a Python manifest."""
    data = ctx.toml(ctx.py("pyproject.toml"))
    up = "" if ctx.py_folder() == "." else "../"
    found = []
    for path, key, value, others in _CACHES:
        table = _table(data, path)
        if table is None or any((ctx.repo / ctx.py(name)).is_file() for name in others) or _in_cache(table.get(key)):
            continue
        dotted = ".".join(path)
        found.append((f"{dotted} {key} is not under .cache/", f'[{dotted}] {key} = "{up}{value}"'))
    return found


def judge(ctx: Context) -> Finding:
    """Pass when no movable file is at the root and every used tool keeps its cache under `.cache/`."""
    at_root = [(name, target) for name, target in MOVABLE.items() if (ctx.repo / name).is_file()]
    caches = _cache_fixes(ctx)
    if not at_root and not caches:
        return passing("tool config is in .config/ and caches are in .cache/ (nothing at the root could move)")
    evidence = [f"{name} at the root" for name, _ in at_root] + [e for e, _ in caches]
    remedy = "; ".join(f"git mv {name} {target}" for name, target in at_root)
    if at_root:
        remedy += (
            ". Then `uv run blueprint gate render`: the rendered recipes pass the new path to each tool; "
            "a flag is needed in every recipe or hook that runs the tool, so a hand-written one must add it"
        )
    if caches:
        remedy += (
            ("; " if remedy else "")
            + "set in the Python manifest: "
            + "; ".join(r for _, r in caches)
            + " (and ignore `.cache/` in .gitignore)"
        )
    return failing(", ".join(evidence), remedy, FixedBy.OWNER)


check(_ID, _STATEMENT, layer="stack")(judge)
