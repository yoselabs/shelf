"""Gate step inputs: every step `check` runs has the files it reads, from the blueprint's defaults plus `gate-inputs.toml` (ADR 0031)."""

from __future__ import annotations

import tomllib

from blueprint import gate_graph
from blueprint.concerns.gate import gate_unreadable
from blueprint.model import Context, Finding, failing, not_applicable, passing

FILE = "gate-inputs.toml"
DEFAULTS = ".blueprint/step-inputs.toml"


def _lists(text: str | None) -> dict[str, list[object]]:
    return {k: v for k, v in tomllib.loads(text or "").items() if isinstance(v, list) and v}


def step_inputs(ctx: Context) -> Finding:
    """Each name `check` hands to `steps` has inputs: the blueprint's default (`.blueprint/step-inputs.toml`) or the repo's own list.

    The repo file holds only its exceptions: a repo's own step (no default) declares its globs there; a known step needs nothing.
    No network. New checkpoints warn first (ADR 0018).
    """
    if (blind := gate_unreadable.unreadable(ctx, "the gate's step inputs")) is not None:
        return blind
    gate = gate_graph.load(ctx)
    if gate is None or not gate.stepped:
        return not_applicable("the gate runs no `steps`")
    known = set(_lists(ctx.read(DEFAULTS))) | set(_lists(ctx.read(FILE)))
    missing = [s for s in gate.stepped if s not in known]
    if missing:
        return failing(f"{', '.join(missing)}: no default inputs from the blueprint and none in {FILE}, so every commit runs them", _REMEDY)
    return passing(f"{len(gate.stepped)} steps have inputs (the blueprint's defaults plus this repo's exceptions)")


_REMEDY = (
    f"run `blueprint gate render` (it writes {DEFAULTS}, the defaults of the steps it knows); for a step of your own add "
    f'`<step> = ["<glob>", ...]` to {FILE}: the files it reads (fnmatch, `*` crosses `/`); `["*"]` when it reads the whole repo. '
    "A step none of whose inputs changed is not started (any-gate)"
)


def narrowed_inputs(ctx: Context) -> Finding:
    """A `[narrow]` entry replaces a step's default inputs with the repo's list, and says why; a widening list needs nothing.

    Narrowing risks a skipped step that a change breaks, so it needs a reason, a list to replace the default with, and a default to narrow.
    """
    text = ctx.read(FILE)
    narrow = tomllib.loads(text).get("narrow") if text else None
    if not isinstance(narrow, dict) or not narrow:
        return not_applicable("no step narrows its default inputs")
    lists, defaults = _lists(text), _lists(ctx.read(DEFAULTS))
    bad = [f"{step}: {why}" for step, reason in narrow.items() if (why := _narrow_fault(step, reason, lists, defaults))]
    if bad:
        return failing(f"[narrow] in {FILE} is wrong: {'; '.join(bad)}", _NARROW_REMEDY)
    return passing(f"{len(narrow)} steps narrow their default inputs, each with its reason")


def _narrow_fault(step: str, reason: object, lists: dict[str, list[object]], defaults: dict[str, list[object]]) -> str:
    if not isinstance(reason, str) or len(reason.strip()) < _MIN_REASON or _trivial(reason):
        return "no reason (a sentence saying which files the step cannot read)"
    if step not in lists:
        return f"no `{step} = [...]` list to replace the default with"
    if step not in defaults:
        return "the blueprint has no default to narrow (a step of your own just declares its list)"
    return ""


_MIN_REASON = 12
_PLACEHOLDERS = frozenset(
    {"todo", "tbd", "fixme", "wip", "na", "n/a", "none", "nothing", "no reason", "same", "same as above", "because", "reason", "later",
     "to be decided", "to be decided later", "not applicable", "unknown", "yes", "no", "ok", "x"}
)  # fmt: skip


def _trivial(reason: str) -> bool:
    """A reason that only looks like one: a placeholder, a word repeated, or no letters worth reading."""
    text = " ".join(reason.lower().split()).strip(" .-:;,!?")
    words = text.split()
    return text in _PLACEHOLDERS or (len(set(words)) == 1 and words[0] in _PLACEHOLDERS) or len(set(text.replace(" ", ""))) <= 2


_NARROW_REMEDY = (
    f'a narrowed step is `<step> = ["<glob>", ...]` plus `[narrow] <step> = "<why the step cannot read the files it drops>"` in {FILE}. '
    "Narrowing can skip a change that breaks the step, so say what makes it safe; to only add files, drop the [narrow] entry"
)


# Why a step may run on any change. Closed: a lazy `*` has no kind to name, so it is found without reading shell.
WIDE_KINDS = {
    "change-set": "its input is the change set itself (a spell check, a secret scan over commits)",
    "self-keyed": "it keys its own inputs finer than the engine can (test units hash what each reaches)",
    "reads-everything": "its answer depends on the whole tree (the blueprint audit, the profile a render is made from)",
    "outside-files": "its answer depends on something outside the tree (git tags, a database, a network service)",
}


def wide_inputs(ctx: Context) -> Finding:
    """A step declared `["*"]` runs on any change; each says why in `[wide]`, with one of `WIDE_KINDS`. New: warns first (ADR 0018).

    The row does not judge what a recipe reads (free-form shell hides tool config files: narrowing from what a script seems to read is
    the worse error). It makes the owner of a `*` say why it is not narrower, from a closed list.
    """
    if (blind := gate_unreadable.unreadable(ctx, "which steps run on any change")) is not None:
        return blind
    gate = gate_graph.load(ctx)
    text = ctx.read(FILE)
    if gate is None or not gate.stepped or text is None:
        return not_applicable("no declared step inputs to judge")
    table = tomllib.loads(text)
    wide = [step for step in gate.stepped if isinstance(table.get(step), list) and "*" in table[step]]
    given = table.get("wide")
    reasons: dict[str, object] = given if isinstance(given, dict) else {}
    unreasoned = [step for step in wide if not _has_kind(reasons.get(step))]
    stale = [step for step in reasons if step not in wide]
    if unreasoned:
        return failing(f"{', '.join(unreasoned)} run on any change and say no reason in [wide] ({FILE})", _WIDE_REMEDY)
    if stale:
        return failing(
            f"[wide] in {FILE} names {', '.join(stale)}, which no longer declares `*`",
            f"delete the stale [wide] entries ({', '.join(stale)})",
        )
    return passing(f"{len(wide)} steps run on any change, each with its reason" if wide else "no step runs on any change")


def _has_kind(reason: object) -> bool:
    return isinstance(reason, str) and any(
        reason.startswith(f"{kind}: ") and not _trivial(reason.removeprefix(f"{kind}: ")) for kind in WIDE_KINDS
    )


_WIDE_REMEDY = (
    f'narrow the step to the files it reads, or add `[wide]` to {FILE} with `<step> = "<kind>: <why>"`; kinds: '
    + "; ".join(f"{kind} ({meaning})" for kind, meaning in WIDE_KINDS.items())
    + ". When unsure what a tool reads (config discovery, lockfiles), keep `*`: an under-declared step skips a change that breaks it"
)
