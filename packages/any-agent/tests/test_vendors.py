"""Each vendor owns its words; `common` and the CLIs' own words join them; a vendor narrows the ladder when the caller names it."""

import pytest

from any_agent import classify, vendors
from any_agent.vendors import anthropic, common, openai, xai


def reason(text, **kw):
    o = classify(1, text, **kw)
    return o.reason if o else None


def test_every_vendor_is_registered_by_name():
    assert sorted(vendors.registry()) == ["anthropic", "common", "openai", "xai"]
    assert [v.name for v in (common.VENDOR, anthropic.VENDOR, openai.VENDOR, xai.VENDOR)] == ["common", "anthropic", "openai", "xai"]


def test_a_vendor_adds_words_to_the_common_ones():
    assert reason("Credit balance is too low") == "credit_exhausted"
    assert reason("Credit balance is too low", only=("anthropic",)) == "credit_exhausted"
    assert reason("Credit balance is too low", only=("openai",)) == "vendor_blip"  # not an OpenAI phrase: only the exit speaks
    assert reason("personal-team-blocked", only=("xai",)) == "credit_exhausted"
    assert reason("Please run /login", only=("anthropic",)) == "logged_out"
    assert reason("Invalid schema for response_format", only=("openai",)) == "bad_request"


def test_the_common_words_hold_for_any_vendor_choice():
    for only in ((), ("anthropic",), ("openai",), ("xai",)):
        assert reason("429 too many requests", only=only) == "rate_limited"
        assert reason("getaddrinfo ENOTFOUND api", only=only) == "network"
        assert reason("401 unauthorized", only=only) == "logged_out"


def test_the_clis_own_words_hold_for_any_vendor_choice():
    assert reason("No conversation found with session ID x", only=("openai",)) == "bad_request"
    assert reason("no rollout found for thread th-1", only=("anthropic",)) == "bad_request"


def test_the_spend_words_are_the_credit_words_and_more():
    w = vendors.words(("xai",))
    assert w.spend.search("billing cycle cap reached") and w.spend.search("spending limit")
    assert not vendors.words(("anthropic",)).spend.search("cycle cap")


def test_an_unknown_vendor_is_an_error_not_a_silent_miss():
    with pytest.raises(KeyError):
        vendors.words(("nobody",))
