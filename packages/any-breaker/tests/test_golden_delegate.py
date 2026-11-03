"""Delegate's incident replays (delegate golden/health_replay.json, taken from the fold this package was promoted from): every row's
admit/refuse/canary/state must come out the same. `fact_of` is the thin consumer side: a delegate run row becomes a Fact or nothing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from any_breaker import OK, OUT, Breaker, Fact, Out, Policy, Rule, State, View

GOLDEN: dict[str, Any] = json.loads((Path(__file__).parent / "golden" / "health_replay.json").read_text(encoding="utf-8"))
POLICY = Policy(
    n=3,
    window_s=600,
    rules={"vendor_blip": Rule(distinct=2), "worker_failed": Rule(distinct=3), "hung": Rule(n=2, window_s=1800, distinct=1)},
    outs={"rate_limited": Out(900), "credit_exhausted": Out(6 * 3600, "probe"), "logged_out": Out(900, "probe")},
)  # fmt: skip
BREAKER = Breaker(POLICY)
LANE_KINDS = ("rate_limited", "credit_exhausted", "logged_out")


def fact_of(r: dict[str, Any]) -> list[Fact]:
    """The lane is a key of its own and `lane|model` another; a run that worked proves both."""
    lane, pair = r["lane"], f"{r['lane']}|{r['model']}"
    if r.get("done"):
        return [Fact(OK, r["ts"], lane), Fact(OK, r["ts"], pair)]
    o = r.get("outcome")
    if o in LANE_KINDS:
        return [Fact(o, r["ts"], lane, until=r.get("until"), note=r.get("say") or "")]
    if o in POLICY.rules:
        return [Fact(o, r["ts"], pair, fp=r.get("fingerprint"), source=r.get("task") or r["run_id"], note=r.get("say") or "")]
    return []


def word(v: View, lane_v: View) -> str:
    if lane_v.state == OUT:
        return "logged_out" if lane_v.kind == "logged_out" else "exhausted"
    return {"open": "broken", "closed": "up"}[v.state]


def decide(state: State, r: dict[str, Any]) -> list[Any]:
    lane_v = BREAKER.view(state, r["lane"], r["ts"])
    pair_v = BREAKER.view(state, f"{r['lane']}|{r['model']}", r["ts"])
    v = lane_v if lane_v.state == OUT else pair_v
    return [r["ts"], v.usable, lane_v.canary or pair_v.canary if v.usable else v.canary, word(pair_v, lane_v)]


@pytest.mark.parametrize("name", ["bad_request_22oct", "grok_other_24oct", "grok_spending_limit_24oct"])
def test_incident_replay_admits_and_refuses_exactly_as_before(name: str) -> None:
    g = GOLDEN[name]
    state, got = State(), []
    for r in g["rows"]:
        d = decide(state, r)
        got.append(d)
        if d[1]:  # a refused launch never ran, so it left no row
            for f in fact_of(r):
                BREAKER.step(state, f)
    assert got == g["decisions"]
    last = g["rows"][-1]["ts"] + 1
    lane_v = BREAKER.view(state, g["lane"], last)
    pair_v = BREAKER.view(state, f"{g['lane']}|{g['model']}", last)
    assert word(pair_v, lane_v) == g["final"]


def test_night_of_22_oct_never_benches() -> None:
    g = GOLDEN["night_22oct"]
    state, got = State(), []
    for r in sorted(g["rows"], key=lambda r: r["ts"]):
        got.append([r["ts"], decide(state, r)[1]])
        for f in fact_of(r):
            BREAKER.step(state, f)
    assert got == g["decisions"]
    assert {k: s.rung for k, s in state.keys.items() if "|" in k} == g["pairs"]
    assert list(state.outs) == g["lanes"]
