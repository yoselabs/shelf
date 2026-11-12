"""Activity: what an agent run did, in the words a person reads, one record per action. `Timeline` folds the harness's typed events
(`any_agent.events`, parsed once from Codex, Claude Code or OpenCode lines) plus the caller's wall-clock time into `Activity` records;
`encode` and `decode` carry one as one JSON line. Display only: nothing here decides whether a run is healthy, stuck or done. A
command or tool is written twice, `running` then `finished` with the same `id`, so a reader keeps the latest of each id."""

import json
from typing import Literal

from any_agent import events as ev
from any_agent._json import Json, opt_int, opt_str, record

Kind = Literal["command", "tool", "message", "error", "waiting"]
State = Literal["running", "finished"]
KINDS: tuple[Kind, ...] = ("command", "tool", "message", "error", "waiting")
STATES: tuple[State, ...] = ("running", "finished")
CAPS: dict[str, int] = {"command": 600, "tool": 300, "message": 2000, "error": 500, "waiting": 200}


@record
class Activity:
    kind: Kind
    state: State
    at: float  # wall-clock seconds: when the action began (a finished record keeps its running record's `at`)
    text: str  # the command, the tool's main argument, the message or the error
    id: str | None = None  # set for a command or tool: its finished record replaces its running one
    name: str = ""  # the tool's name
    waited_ms: int | None = None  # the agent's gap: the previous action's end to this one's start
    duration_ms: int | None = None  # only when finished
    exit_code: int | None = None  # a finished command's, when the harness reported one


def _cut(kind: str, text: str) -> str:
    cap = CAPS[kind]
    return text if len(text) <= cap else text[: cap - 1] + "…"


def _ms(seconds: float) -> int:
    return max(0, round(seconds * 1000))


class Timeline:
    """One run's folding state: the open commands and tools by id and the end of the last action. Feed events in order with the time
    each arrived; the result of `add` is the records to append."""

    def __init__(self) -> None:
        self._open: dict[str, tuple[float, int | None]] = {}
        self._end: float | None = None
        self._count = 0

    def _waited(self, now: float) -> int | None:
        return None if self._end is None else _ms(now - self._end)

    def _begin(self, kind: Kind, ident: str | None, now: float, text: str, name: str = "") -> Activity:
        self._count += 1
        key = ident or f"n{self._count}"
        waited = self._waited(now)
        self._open[key] = (now, waited)
        return Activity(kind=kind, state="running", at=now, text=_cut(kind, text), id=key, name=name, waited_ms=waited)

    def _finish(
        self, kind: Kind, ident: str | None, now: float, text: str, secs: float | None, name: str = "", exit_code: int | None = None
    ) -> Activity:
        started, waited = self._open.pop(ident, (None, None)) if ident else (None, None)
        self._end = now
        took = _ms(secs) if secs is not None else None if started is None else _ms(now - started)
        return Activity(
            kind=kind,
            state="finished",
            at=now if started is None else started,
            text=_cut(kind, text),
            id=ident,
            name=name,
            waited_ms=waited,
            duration_ms=took,
            exit_code=exit_code,
        )

    def _once(self, kind: Kind, now: float, text: str) -> Activity:
        found = Activity(kind=kind, state="finished", at=now, text=_cut(kind, text), waited_ms=self._waited(now))
        self._end = now
        return found

    def add(self, event: ev.HarnessEvent, now: float) -> list[Activity]:
        found: Activity | None = None
        match event:
            case ev.Cmd():
                found = self._begin("command", event.id, now, event.text)
            case ev.CmdEnd():
                found = self._finish("command", event.id, now, event.text, event.secs, exit_code=event.exit)
            case ev.Tool():
                found = self._begin("tool", event.id, now, event.arg, event.name)
            case ev.ToolEnd():
                found = self._finish("tool", event.id, now, event.arg, event.secs, event.name)
            case ev.Msg() if event.text.strip():
                found = self._once("message", now, event.text)
            case ev.HarnessError():
                found = self._once("error", now, event.text)
            case ev.Reconnecting() | ev.WaitingForNetwork():
                found = self._once("waiting", now, event.text or "waiting for the network")
            case ev.Stall():
                found = self._once("waiting", now, f"no output for {round(event.secs)} s")
        return [] if found is None else [found]


def encode(a: Activity) -> str:
    """One JSON line, no newline."""
    optional: tuple[tuple[str, Json], ...] = (("id", a.id), ("n", a.name), ("w", a.waited_ms), ("d", a.duration_ms), ("x", a.exit_code))
    fields: dict[str, Json] = {"k": a.kind, "s": a.state, "at": a.at, "t": a.text}
    fields.update({k: v for k, v in optional if v not in (None, "")})
    return json.dumps(fields, separators=(",", ":"))


def decode(line: str) -> Activity | None:
    """The record `line` holds, or None for anything that is not one of ours (a truncation marker, a cut line, other JSON)."""
    try:
        raw = json.loads(line)
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    kind, state, at, body = raw.get("k"), raw.get("s"), raw.get("at"), raw.get("t")
    if kind not in KINDS or state not in STATES or not isinstance(at, int | float) or isinstance(at, bool) or not isinstance(body, str):
        return None
    return Activity(
        kind=kind,
        state=state,
        at=float(at),
        text=body,
        id=opt_str(raw.get("id")),
        name=opt_str(raw.get("n")) or "",
        waited_ms=opt_int(raw.get("w")),
        duration_ms=opt_int(raw.get("d")),
        exit_code=opt_int(raw.get("x")),
    )
