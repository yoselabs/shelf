"""`layout.one-config-per-tool`: a tool's config is defined once per repo; a project that differs extends the shared base (ADR 0035).

The same tool configured in two project folders with identical or near-identical content is a copy that will drift. The remedy is the
tool's own extend mechanism (a project then carries only the delta), or, for a tool with none, a waiver with a reason.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint.model import Context, Finding, FixedBy, check, failing, passing, toml_table, walk

if TYPE_CHECKING:
    from collections.abc import Callable

_ID = "layout.one-config-per-tool"
_STATEMENT = (
    "a tool's config is defined once per repo: a project that differs extends the shared base and carries only the delta (ADR 0035)"
)
_MIN_ITEMS = 3  # a config with fewer settings is not worth a base
_SAME = 0.7  # Jaccard share of settings at or above which two configs are one copy
_DEPTH = 4
# Folders whose configs are inputs the repo judges or teaches with, never the repo's own settings.
_NOT_OURS = frozenset({"fixtures", "examples", "testdata", "vendor", "third_party", "site-packages"})


@dataclass(frozen=True)
class Tool:
    """A tool whose config can be copied: the file names, and the way a project extends a shared base (None: the tool cannot)."""

    name: str
    files: tuple[str, ...]
    base: str
    extend: Callable[[str], str] | None
    keys: tuple[str, ...] = ("extend", "extends")


TOOLS = (
    Tool("ruff", ("ruff.toml", ".ruff.toml"), "ruff.toml", lambda rel: f'extend = "{rel}" in its ruff.toml (or `[tool.ruff] extend`)'),
    Tool("tsconfig", ("tsconfig.json",), "tsconfig.base.json", lambda rel: f'"extends": "{rel}" in its tsconfig.json'),
    Tool("biome", ("biome.json", "biome.jsonc"), "biome.json", lambda rel: f'"extends": ["{rel}"] in its biome.json'),
    Tool("eslint", (".eslintrc.json",), ".eslintrc.base.json", lambda rel: f'"extends": "{rel}" in its .eslintrc.json'),
    Tool(
        "gitleaks",
        (".gitleaks.toml", "gitleaks.toml"),
        ".config/gitleaks.toml",
        lambda rel: f'`[extend] path = "{rel}"` in its gitleaks.toml',
        ("extend",),
    ),
    Tool("hadolint", (".hadolint.yaml", "hadolint.yaml"), ".config/hadolint.yaml", None),
    Tool("yamlfmt", (".yamlfmt.yaml", ".yamlfmt"), ".config/yamlfmt.yaml", None),
    Tool("dclint", (".dclintrc", ".dclintrc.json", "dclintrc.json"), ".config/dclintrc.json", None),
    Tool("typos", ("typos.toml", "_typos.toml", ".typos.toml"), ".config/typos.toml", None),
    Tool("prettier", (".prettierrc", ".prettierrc.json", "prettier.config.json"), ".prettierrc", None),
)

_COMMENT = re.compile(r"^\s*(//|#)")


def _flatten(value: object, prefix: str = "") -> set[str]:
    """Every leaf setting as `dotted.key=value` (a list is one leaf per element), so two configs compare setting by setting."""
    if isinstance(value, dict):
        out: set[str] = set()
        for key, child in value.items():
            out |= _flatten(child, f"{prefix}{key}.")
        return out
    if isinstance(value, list):
        return {f"{prefix}[]={item!r}" for item in value} or {f"{prefix}[]"}
    return {f"{prefix}={value!r}"}


def _config_lines(text: str) -> set[str]:
    """The non-comment lines of a config that is neither TOML nor JSON (YAML and the like): the settings, line by line."""
    return {line.strip() for line in text.splitlines() if line.strip() and not _COMMENT.match(line)}


def _read_config(ctx: Context, rel: str, text: str) -> dict[str, object] | set[str]:
    """The parsed TOML or JSON object of a config; the non-comment lines for anything else (YAML, or JSON with trailing commas)."""
    if rel.endswith(".toml"):
        return ctx.toml(rel) or _config_lines(text)
    if rel.endswith((".json", ".jsonc", "rc")):
        body = "\n".join(line for line in text.splitlines() if not _COMMENT.match(line))
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return _config_lines(text)
        return data if isinstance(data, dict) else _config_lines(text)
    return _config_lines(text)


def _extends(data: object, tool: Tool) -> bool:
    if not isinstance(data, dict):
        return False
    if tool.name == "gitleaks":
        ext = data.get("extend")
        return isinstance(ext, dict) and "path" in ext
    return any(k in data for k in tool.keys)


def _definitions(ctx: Context, tool: Tool) -> list[tuple[str, set[str]]]:
    """`(repo-relative file, settings)` of every definition of `tool` that is not already an extension, within `_DEPTH` folders."""
    found: list[tuple[str, set[str]]] = []
    for name in tool.files:
        for path in walk(ctx.repo, name, _DEPTH):
            rel = path.relative_to(ctx.repo).as_posix()
            if _NOT_OURS & set(Path(rel).parts) or "/tests/" in f"/{rel}":
                continue
            text = ctx.read(rel) or ""
            data = _read_config(ctx, rel, text)
            if _extends(data, tool):
                continue
            items = _flatten(data) if isinstance(data, dict) else data
            found.append((rel, items))
    if tool.name == "ruff":
        for path in walk(ctx.repo, "pyproject.toml", _DEPTH):
            rel = path.relative_to(ctx.repo).as_posix()
            if _NOT_OURS & set(Path(rel).parts) or "/tests/" in f"/{rel}":
                continue
            table = toml_table(ctx.toml(rel), "tool", "ruff")
            if table and "extend" not in table:
                found.append((rel, _flatten(table)))
    return [(rel, items) for rel, items in found if len(items) >= _MIN_ITEMS]


def _same(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def _up(rel: str) -> str:
    """The path from the folder of `rel` back to the repo root."""
    return "../" * len(Path(rel).parent.parts)


def judge(ctx: Context) -> Finding:
    """Pass unless one tool has two definitions that are copies of each other; name the pair and the tool's extend mechanism."""
    evidence: list[str] = []
    remedies: list[str] = []
    for tool in TOOLS:
        defs = _definitions(ctx, tool)
        for i, (first, a) in enumerate(defs):
            for second, b in defs[i + 1 :]:
                share = _same(a, b)
                if share < _SAME:
                    continue
                evidence.append(f"{tool.name}: {first} and {second} ({round(share * 100)}% the same settings)")
                if tool.extend is None:
                    remedies.append(f"{tool.name} cannot extend: waive with a reason, or keep one file at {tool.base} and pass it by flag")
                else:
                    base = f"{_up(second)}{tool.base}"
                    remedies.append(
                        f"{tool.name}: move the shared settings to {tool.base}, then {tool.extend(base)} carrying only the delta"
                    )
    if evidence:
        return failing("; ".join(evidence), "; ".join(dict.fromkeys(remedies)), FixedBy.OWNER)
    return passing("each tool's config is defined once, or extends a shared base")


check(_ID, _STATEMENT, layer="stack")(judge)
