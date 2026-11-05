"""The outcome ladder, replayed on 488 rows of evidence taken from real runs (fixtures/), then its order."""

import json
from pathlib import Path

import pytest

from any_agent import classify
from any_agent.classify import Outcome, limit_words, network_stop, says_login, says_spend, with_network

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.json"))


def rows():
    for path in FIXTURES:
        f = json.loads(path.read_text(encoding="utf-8"))
        for row in f["rows"]:
            if "evidence" in row:
                yield pytest.param(row["evidence"], row.get("expected_reason", f.get("expected_reason")), id=f"{path.stem}:{row['id']}")


@pytest.mark.parametrize(("ev", "want"), list(rows()))
def test_a_row_of_a_real_run_replays_to_its_reason(ev, want):
    o = classify(ev["rc"], ev["vendor_err"], ev["stderr"], ev["timed_out"], ev["work_seen"], ev["structured"])
    assert (o.reason if o else None) == want


def test_the_fixtures_are_all_there():
    assert len(list(rows())) > 400


def reason(*a, **kw):
    o = classify(*a, **kw)
    return o.reason if o else None


def test_a_clean_exit_is_done():
    assert classify(0) is None


def test_our_own_facts_come_before_the_vendors_words():
    assert reason(1, "429 rate limit", structured={"secret": "cat ~/.ssh/id"}) == "secrets"
    assert reason(1, structured={"watchdog": "limit", "msg": "credit balance is too low"}) == "credit_exhausted"
    assert reason(-15, structured={"watchdog": "limit", "msg": "usage limit"}) == "rate_limited"
    assert reason(-15, structured={"watchdog": "hung", "net_up": False}) == "network"
    assert reason(-15, structured={"watchdog": "hung"}) == "hung"
    assert reason(-15, timed_out=True) == "timeout"


def test_a_measured_status_comes_before_words():
    assert reason(1, "boom", structured={"http_status": 429}) == "rate_limited"
    assert reason(1, "boom", structured={"http_status": 401}) == "logged_out"
    assert reason(1, "boom", structured={"http_status": 400}) == "bad_request"


def test_the_vendors_words_name_the_reason():
    assert reason(1, "You have hit your usage limit") == "rate_limited"
    assert reason(1, "Credit balance is too low") == "credit_exhausted"
    assert reason(1, "Not logged in") == "logged_out"
    assert reason(1, "invalid_request_error") == "bad_request"
    assert reason(1, "No conversation found with session ID x") == "bad_request"
    assert reason(1, "no rollout found for thread th-1") == "bad_request"
    assert reason(1, 'turn failed {"status": 400}') == "bad_request"
    assert reason(1, 'turn failed {"status": 429}') == "rate_limited"
    assert reason(1, "getaddrinfo ENOTFOUND api") == "network"


def test_a_network_word_after_work_was_done_is_the_workers_failure():
    assert reason(1, "getaddrinfo ENOTFOUND api", work_seen=True) == "worker_failed"


def test_the_exit_code_answers_when_no_words_matched():
    assert reason(-9) == "killed"
    assert reason(1, "something odd") == "vendor_blip"
    assert reason(1, "something odd", work_seen=True) == "worker_failed"
    o = classify(2, "", "stderr tail")
    assert o is not None and o.source == "stderr"
    assert reason(3) == "worker_failed"


def test_stderr_counts_only_on_a_failed_exit():
    assert classify(0, "", "rate limit in a log line") is None


def test_helpers_read_words():
    assert says_login("Please run /login") and not says_login("all fine")
    assert says_spend("spending limit reached") and says_spend("top up your billing")
    assert limit_words("weekly cap", None) == "weekly limit hit"
    assert limit_words("Free usage exceeded", None) == "free usage limit reached"
    assert limit_words("nothing", "5-hour") == "5-hour limit hit"
    assert limit_words("nothing", None) == "usage limit hit"


def test_a_lane_mark_for_credit_or_login_is_its_own_reason_whatever_the_words():
    assert reason(-15, structured={"watchdog": "credit", "msg": "marked out"}) == "credit_exhausted"
    assert reason(-15, structured={"watchdog": "logged_out", "msg": "usage limit"}) == "logged_out"


def test_with_network_turns_only_a_cause_less_failure_into_the_network():
    down, up = (lambda: False), (lambda: True)
    assert with_network(Outcome("hung", "", "ours"), down).reason == "network"
    assert with_network(Outcome("hung", "", "ours"), up).reason == "hung"
    assert with_network(Outcome("worker_failed", "ECONNRESET", "event"), up).reason == "network"
    assert with_network(Outcome("rate_limited", "429", "event"), down).reason == "rate_limited"
    assert network_stop("waiting for network") == Outcome("network", "waiting for network", "event")
