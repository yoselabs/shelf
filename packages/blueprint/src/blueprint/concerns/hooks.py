"""Hook anti-patterns (mission blueprint-multi-stack-contracts, design D6): what a hook config does that costs a commit or hides a failure.

`.pre-commit-config.yaml` is read as text, a block per `- id:` (blueprint has no YAML dependency). Every finding names the hook and the
line to change or delete. The pre-push gate itself, bd's events and the installed files are `gate.hooks-recipe` and `gate.hooks-installed`.

Deviation from D6's "the gate also called by another hook": a post-merge gate is allowed. `any-gate` skips a tree that already
passed, so the
second call costs nothing, and the shelf runs one there on purpose (a merge made elsewhere lands a tree no local gate saw, 2026-11-19).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueprint.model import check, failing, not_applicable, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_CONFIG = ".pre-commit-config.yaml"
_NONE = f"no {_CONFIG}: nothing to judge (gate.hooks-recipe asks for one)"
_ID = re.compile(r"^\s*-\s*id:\s*['\"]?([\w./-]+)", re.MULTILINE)
_STAGES = re.compile(r"^\s*stages:\s*\[(.*?)\]", re.MULTILINE)
_ENTRY = re.compile(r"^\s*entry:\s*(.+?)\s*$", re.MULTILINE)
# Per-commit stages: a hook here delays every commit, so it must be fast. A hook with no `stages:` runs at pre-commit.
_AT_COMMIT = {"pre-commit", "commit", "prepare-commit-msg", "commit-msg", "pre-merge-commit"}
_TESTS = re.compile(
    r"\bpytest\b|\bjust\s+(?:check|test)\b|\bmake\s+(?:check|test)\b|\bdotnet\s+test\b|\bnpm\s+(?:run\s+)?test\b|\bcargo\s+test\b|\bgo\s+test\b"
    r"|\byarn\s+test\b|\bpnpm\s+(?:run\s+)?test\b"
)
_GATE = re.compile(r"\b(?:just|make)\s+check\b")
_BD = re.compile(r"\bbd\s+(?:hooks\s+run|dolt\s+push)\b")
_ALWAYS_OK = re.compile(r"\|\|\s*(?:true|exit\s+0|:)(?!\w)|;\s*exit\s+0\s*['\"]?\s*$")
_CLONE = re.compile(r"\bSHELF_HOME\b|\.\./shelf\b|~/Workspaces/shelf|\$HOME/Workspaces/shelf|\$\{HOME\}/Workspaces/shelf")


@dataclass(frozen=True)
class Hook:
    id: str
    line: int
    text: str
    stages: frozenset[str]
    entry: str

    @property
    def at_commit(self) -> bool:
        return bool(self.stages & _AT_COMMIT)


def _hooks(config: str) -> list[Hook]:
    found = list(_ID.finditer(config))
    ends = [m.start() for m in found[1:]] + [len(config)]
    hooks: list[Hook] = []
    for m, end in zip(found, ends, strict=True):
        text = config[m.start() : end]
        stages = _STAGES.search(text)
        names = {s.strip().strip("'\"") for s in stages.group(1).split(",")} if stages else {"pre-commit"}
        entry = _ENTRY.search(text)
        hooks.append(Hook(m.group(1), config.count("\n", 0, m.start()) + 1, text, frozenset(names - {""}), entry.group(1) if entry else ""))
    return hooks


def _is_gate(hook: Hook) -> bool:
    return "pre-push" in hook.stages and bool(_GATE.search(hook.entry))


def _named(hooks: list[Hook]) -> str:
    return ", ".join(f"{h.id} (line {h.line})" for h in hooks)


@check("hooks.no-tests-at-commit", "no hook that runs at commit time runs the test suite or the gate: tests belong to the pre-push gate")
def no_tests_at_commit(ctx: Context) -> Finding:
    """A commit is the fastest loop a person has; a suite in it is skipped with --no-verify, and then nothing guards the push."""
    config = ctx.read(_CONFIG)
    if config is None:
        return not_applicable(_NONE)
    slow = [h for h in _hooks(config) if h.at_commit and _TESTS.search(h.entry)]
    if slow:
        return failing(
            f"a commit-time hook runs tests: {_named(slow)}",
            "set `stages: [pre-push]` on it, or delete it: the pre-push `gate` hook runs `just check`; commit hooks stay format and lint",
        )
    return passing("no commit-time hook runs tests or the gate")


@check("hooks.pre-push-is-the-gate", "the only pre-push hooks are the gate and bd's own: no second, partial gate")
def pre_push_is_the_gate(ctx: Context) -> Finding:
    """A pre-push lint or test beside the gate disagrees with it, and one of the two is what people trust."""
    config = ctx.read(_CONFIG)
    if config is None:
        return not_applicable(_NONE)
    extra = [h for h in _hooks(config) if "pre-push" in h.stages and not _is_gate(h) and not _BD.search(h.entry)]
    if extra:
        return failing(
            f"pre-push runs something other than the gate: {_named(extra)}",
            "move its check into a `just check` step and delete the hook",
        )
    return passing("pre-push runs the gate and bd's events only")


@check("hooks.fail-closed", "no hook swallows its own failure (`|| true`, a trailing `exit 0`)")
def fail_closed(ctx: Context) -> Finding:
    """A hook that cannot fail says nothing: a2kay's push `Passed` while the Dolt push failed."""
    config = ctx.read(_CONFIG)
    if config is None:
        return not_applicable(_NONE)
    soft = [h for h in _hooks(config) if _ALWAYS_OK.search(h.entry)]
    if soft:
        return failing(
            f"a hook exits 0 whatever happens: {_named(soft)}",
            "delete the `|| true` or `exit 0`; an optional step prints FAILED and exits non-zero unless an env var allows it",
        )
    return passing("no hook ends in an unconditional exit 0")


@check(
    "hooks.no-clone-path",
    "no hook is resolved through a shelf clone (SHELF_HOME, ../shelf, ~/Workspaces/shelf): the tool is a pinned dependency",
)
def no_clone_path(ctx: Context) -> Finding:
    """A path into a clone is another machine's layout: the hook breaks (or silently skips) on a fresh checkout and in a worktree."""
    config = ctx.read(_CONFIG)
    if config is None:
        return not_applicable(_NONE)
    bad = [h for h in _hooks(config) if any(_CLONE.search(ln) for ln in h.text.splitlines() if not ln.lstrip().startswith("#"))]
    if bad:
        return failing(
            f"a hook reaches into a shelf clone: {_named(bad)}",
            "run it through the pinned dependency instead (`uv run blueprint gate guard`, `uv run python -m any_gate ...`)",
        )
    return passing("no hook path goes through a shelf clone")


@check(
    "hooks.gate-always-runs",
    "the pre-push gate hook sets always_run and has no files filter, so a push cannot skip it by touching other files",
)
def gate_always_runs(ctx: Context) -> Finding:
    """prek skips a hook whose `files` match nothing, so a gate with a filter is skipped by a push that touches other files."""
    config = ctx.read(_CONFIG)
    if config is None:
        return not_applicable(_NONE)
    gates = [h for h in _hooks(config) if _is_gate(h)]
    if not gates:
        return not_applicable("no pre-push gate hook (gate.hooks-recipe asks for one)")
    leaky = [
        h
        for h in gates
        if not re.search(r"^\s*always_run:\s*true\b", h.text, re.MULTILINE)
        or re.search(r"^\s*(?:files|exclude|types):", h.text, re.MULTILINE)
    ]
    if leaky:
        return failing(
            f"the gate hook can be skipped (no `always_run: true`, or a files/exclude/types filter): {_named(leaky)}",
            "give it `always_run: true` and `pass_filenames: false`, and remove its `files`, `exclude` and `types` keys",
        )
    return passing("the gate hook always runs")
