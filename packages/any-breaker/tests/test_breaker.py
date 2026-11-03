from __future__ import annotations

import json

import pytest

from any_breaker import CLOSED, OK, OPEN, OUT, RELEASE, Breaker, Fact, Out, Policy, Rule, State

POL = Policy(
    n=3, window_s=600, rules={"blip": Rule(distinct=2), "fail": Rule(distinct=3), "hung": Rule(n=2, window_s=1800)},
    outs={"limit": Out(900), "credit": Out(6 * 3600, "probe")},
)  # fmt: skip
B = Breaker(POL)


def fail(ts: float, kind: str = "blip", *, key: str = "k", source: str | None = None, fp: str = "same", note: str = "") -> Fact:
    return Fact(kind, ts, key, fp=fp, source=source or f"t{ts}", note=note)


def test_n_identical_failures_from_distinct_sources_open_the_breaker_for_the_first_rung() -> None:
    s = B.fold([fail(1000, source="a"), fail(1060, source="a"), fail(1120, source="b", note="Server error.")])
    v = B.view(s, "k", 1121)
    assert (v.state, v.usable, v.kind, v.source, v.rung) == (OPEN, False, "blip", "breaker", 1)
    assert v.until == 1120 + 900
    assert v.evidence == "Server error."
    assert len(v.recent) == 3


def test_one_source_failing_again_and_again_opens_nothing() -> None:
    s = B.fold([fail(1000 + 60 * i, source="same") for i in range(5)])
    assert B.view(s, "k", 1400).usable


def test_different_fingerprints_do_not_add_up() -> None:
    s = B.fold([fail(1000, fp="a"), fail(1060, fp="b"), fail(1120, fp="c")])
    assert B.view(s, "k", 1130).usable


def test_failures_outside_the_window_do_not_count() -> None:
    s = B.fold([fail(1000), fail(1000 + 660), fail(1000 + 1320)])
    assert B.view(s, "k", 1000 + 1380).usable


def test_a_failure_with_no_fp_is_fingerprinted_by_its_kind() -> None:
    s = B.fold([Fact("blip", 1000 + i, "k", source=f"t{i}") for i in range(3)])
    assert not B.view(s, "k", 1010).usable


def test_an_ok_resets_the_streak_and_the_ladder() -> None:
    s = B.fold([fail(1000), fail(1010), Fact(OK, 1020, "k"), fail(1030)])
    assert B.view(s, "k", 1040).usable


def test_the_ladder_climbs_15_30_60_then_stays_and_a_passing_canary_resets_it() -> None:
    s = State()
    for i in range(3):
        B.step(s, fail(1000 + i, "fail"))
    at, minutes = 1002.0, []
    for _ in range(4):
        v = B.view(s, "k", at + 1)
        assert (v.state, v.usable) == (OPEN, False)
        assert v.until is not None
        minutes.append(round((v.until - at) / 60))
        at = v.until + 1  # the bench ends: the next launch is the canary...
        v = B.view(s, "k", at)
        assert (v.state, v.usable, v.canary) == (CLOSED, True, True)
        B.step(s, fail(at, "fail", source="canary"))  # ...and it fails: the next rung starts at once
    assert minutes == [15, 30, 60, 60]
    t = B.view(s, "k", at + 1).until
    assert t is not None
    B.step(s, Fact(OK, t + 1, "k"))
    v = B.view(s, "k", t + 2)
    assert (v.state, v.rung, v.canary) == (CLOSED, 0, False)


def test_a_failure_launched_before_the_bench_began_is_not_counted_again() -> None:
    s = B.fold([fail(1000, "fail"), fail(1001, "fail"), fail(1002, "fail")])
    until = B.view(s, "k", 1003).until
    B.step(s, fail(1003, "fail"))
    assert B.view(s, "k", 1004).until == until


def test_a_kind_rule_overrides_the_default() -> None:
    s = B.fold([fail(1000, "hung"), fail(1000 + 1200, "hung")])
    assert B.view(s, "k", 1000 + 1260).kind == "hung"
    s = B.fold([fail(1000, "hung"), fail(1000 + 2400, "hung")])
    assert B.view(s, "k", 1000 + 2460).usable


def test_keys_are_independent() -> None:
    s = B.fold([fail(1000 + i, "fail", key="a") for i in range(3)])
    assert not B.view(s, "a", 1010).usable
    assert B.view(s, "b", 1010).usable


def test_an_out_with_the_vendors_time_ends_there_and_then_one_canary() -> None:
    s = B.fold([Fact("limit", 1000, "k", until=5000.0, note="limit")])
    v = B.view(s, "k", 2000)
    assert (v.state, v.usable, v.source, v.until) == (OUT, False, "vendor", 5000.0)
    v = B.view(s, "k", 5001)
    assert (v.state, v.usable, v.canary) == (CLOSED, True, True)


def test_an_out_without_a_time_waits_the_kinds_own_wait() -> None:
    limit = B.view(B.fold([Fact("limit", 1000, "k")]), "k", 1001)
    credit = B.view(B.fold([Fact("credit", 1000, "k")]), "k", 1001)
    assert (limit.source, limit.until) == ("guess", 1900)
    assert (credit.source, credit.until) == ("probe", 1000 + 6 * 3600)


def test_an_unlock_time_in_the_past_is_ignored() -> None:
    assert B.view(B.fold([Fact("limit", 1000, "k", until=900.0)]), "k", 1001).source == "guess"


@pytest.mark.parametrize("clearing", [Fact(OK, 1100, "k"), Fact(RELEASE, 1100, "k")])
def test_an_ok_or_a_release_ends_an_out(clearing: Fact) -> None:
    s = B.fold([Fact("limit", 1000, "k", until=9e9), clearing])
    assert B.view(s, "k", 1200).usable


def test_a_prefix_release_clears_every_key_under_it() -> None:
    facts = (
        [Fact("limit", 1000, "L", until=9e9)]
        + [fail(1000 + i, "fail", key="L|m") for i in range(3)]
        + [fail(1000 + i, "fail", key="M|m") for i in range(3)]
    )
    s = B.fold([*facts, Fact(RELEASE, 1100, "L", prefix=True)])
    assert B.view(s, "L", 1200).usable and B.view(s, "L|m", 1200).usable
    assert not B.view(s, "M|m", 1200).usable


def test_fold_is_associative_over_a_checkpoint() -> None:
    facts = [fail(1000 + 40 * i, "fail" if i % 3 else "blip", key="a" if i % 2 else "b") for i in range(40)] + [Fact("limit", 1900, "c")]
    facts.sort(key=lambda f: f.ts)
    for cut in (0, 1, 7, 20, 39, 41):
        assert B.fold(facts[cut:], B.fold(facts[:cut])) == B.fold(facts)


def test_fold_leaves_the_checkpoint_untouched() -> None:
    head = B.fold([fail(1000)])
    before = head.to_dict()
    B.fold([fail(1100), fail(1200)], head)
    assert head.to_dict() == before


def test_fold_sorts_a_batch_by_time() -> None:
    facts = [fail(1000 + i, "fail") for i in range(3)]
    assert B.fold(reversed(facts)) == B.fold(facts)


def test_a_state_survives_json() -> None:
    s = B.fold([fail(1000 + i, "fail") for i in range(3)] + [Fact("limit", 1010, "o", until=9e9)])
    assert State.from_dict(json.loads(json.dumps(s.to_dict()))) == s


def test_recent_failures_keep_the_last_three() -> None:
    s = B.fold([fail(1000 + i, "blip", source="a") for i in range(5)])
    assert [f.ts for f in B.view(s, "k", 1010).recent] == [1002, 1003, 1004]


def test_a_policy_needs_a_rung() -> None:
    with pytest.raises(ValueError, match="rung"):
        Policy(ladder_s=())


def test_a_default_policy_breaker_counts_three_in_ten_minutes() -> None:
    b = Breaker()
    s = b.fold([Fact("x", 1000 + i, "k") for i in range(3)])
    assert not b.view(s, "k", 1010).usable
