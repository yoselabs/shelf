"""Which ruff rules a repo's lint config selects, read from the parsed TOML (a text match let `ignore = ["S"]` pass)."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blueprint.model import Context

# ruff's own precedence: the first of these that holds a lint table is the config.
_FILES = (".ruff.toml", "ruff.toml", "pyproject.toml")


def _lint_table(ctx: Context) -> dict[str, Any] | None:
    for rel in _FILES:
        text = ctx.read(ctx.py(rel))
        if text is None:
            continue
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            continue
        ruff = data.get("tool", {}).get("ruff", {}) if rel == "pyproject.toml" else data
        lint = ruff.get("lint") if isinstance(ruff, dict) else None
        if isinstance(lint, dict):
            return lint
    return None


def _names(table: dict[str, Any], *keys: str) -> list[str]:
    return [str(v) for k in keys for v in (table.get(k) or []) if isinstance(table.get(k), list)]


def _covers(entry: str, code: str) -> bool:
    return entry == "ALL" or code.startswith(entry) or (code == "C90" and entry == "C901")


def selects(ctx: Context, code: str) -> bool:
    """Whether the lint config selects the rule family `code` (`S`, `C90`) and does not ignore it."""
    table = _lint_table(ctx)
    if table is None:
        return False
    chosen = any(_covers(e, code) for e in _names(table, "select", "extend-select"))
    ignored = any(_covers(e, code) for e in _names(table, "ignore", "extend-ignore"))
    return chosen and not ignored


def excluded(ctx: Context) -> tuple[str, ...]:
    """The path patterns ruff skips: `exclude` and `extend-exclude` of the first config that sets either."""
    for rel in _FILES:
        text = ctx.read(ctx.py(rel))
        if text is None:
            continue
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            continue
        ruff = data.get("tool", {}).get("ruff", {}) if rel == "pyproject.toml" else data
        patterns: list[str] = _names(ruff, "exclude", "extend-exclude") if isinstance(ruff, dict) else []
        if patterns:
            return tuple(p for pat in patterns for p in (pat, f"{pat.rstrip('/')}/*"))
    return ()
