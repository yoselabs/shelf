"""Acceptance suite for the llm-wobble funnel.

Ported from a2web's `test_wobble.py`, rewritten to exercise the PUBLIC funnel
(`parse_with_policy` / `parse_list_with_policy`) rather than the retired
`apply_policy` direct-call shim — the funnel is the promoted contract, so through
it a STRICT miss surfaces as `ParseError` (not a bare `KeyError`) and `WobbleSkip`
propagates for caller short-circuiting.
"""

from __future__ import annotations

import json
import logging

import pytest
from llm_wobble import (
    ParseError,
    WobblePolicy,
    WobbleSkip,
    WobbleTolerance,
    _first_json_object,
    emit_wobble,
    parse_list_with_policy,
    parse_with_policy,
    recovered_fields,
    strip_fenced_blocks,
    unwrap,
)

_TEST_LOGGER = logging.getLogger("llm_wobble_test")


def _resolve(parsed: dict[str, object], field: str, policy: WobblePolicy) -> object:
    """Apply a single-field policy through the real funnel and return the value."""
    wobbled = parse_with_policy(
        json.dumps(parsed),
        policies={field: policy},
        into=lambda d: d.get(field),
        boundary="test",
        model="m",
        logger=_TEST_LOGGER,
    )
    return unwrap(wobbled)


def _events(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == "llm_wobble"]


# --------------------------------------------------------------------- #
# Per-field policy resolution
# --------------------------------------------------------------------- #


def test_strict_present_returns_value() -> None:
    assert _resolve({"x": 5}, "x", WobblePolicy(WobbleTolerance.STRICT)) == 5


def test_strict_missing_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="missing required field"):
        _resolve({}, "x", WobblePolicy(WobbleTolerance.STRICT))


def test_derive_calls_callable_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    policy = WobblePolicy(WobbleTolerance.DERIVE, derive=lambda p: int(p["base"]) * 2)
    with caplog.at_level(logging.WARNING, logger=_TEST_LOGGER.name):
        out = _resolve({"base": 3}, "x", policy)
    assert out == 6
    events = _events(caplog)
    assert len(events) == 1
    assert events[0].fields["field"] == "x"  # ty: ignore[unresolved-attribute] - set via logging `extra`
    assert events[0].fields["tolerance"] == "derive"  # ty: ignore[unresolved-attribute]


def test_default_substitutes_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=_TEST_LOGGER.name):
        out = _resolve({}, "x", WobblePolicy(WobbleTolerance.DEFAULT, default="fallback"))
    assert out == "fallback"
    events = _events(caplog)
    assert len(events) == 1
    assert events[0].fields["tolerance"] == "default"  # ty: ignore[unresolved-attribute]


def test_skip_raises_wobbleskip_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=_TEST_LOGGER.name), pytest.raises(WobbleSkip):
        _resolve({}, "x", WobblePolicy(WobbleTolerance.SKIP))
    events = _events(caplog)
    assert len(events) == 1
    assert events[0].fields["tolerance"] == "skip"  # ty: ignore[unresolved-attribute]


def test_null_value_treated_as_missing() -> None:
    """Explicit null is the same wobble as omission — recover via the policy."""
    assert _resolve({"x": None}, "x", WobblePolicy(WobbleTolerance.DEFAULT, default="ok")) == "ok"


def test_derive_without_callable_raises_parse_error() -> None:
    """DERIVE policy with no `derive` callable is a mis-declared policy."""
    with pytest.raises(ParseError):
        _resolve({}, "x", WobblePolicy(WobbleTolerance.DERIVE))


def test_recovered_fields_names_the_recovery() -> None:
    wobbled = parse_with_policy(
        json.dumps({"a": 1}),
        policies={"a": WobblePolicy(WobbleTolerance.STRICT), "b": WobblePolicy(WobbleTolerance.DEFAULT, default=0)},
        into=dict,
        boundary="test",
        model="m",
    )
    assert recovered_fields(wobbled) == ("b",)


# --------------------------------------------------------------------- #
# Envelope decode + recovery
# --------------------------------------------------------------------- #


def test_strips_json_fence() -> None:
    wobbled = parse_with_policy(
        '```json\n{"x": 1}\n```',
        policies={"x": WobblePolicy(WobbleTolerance.STRICT)},
        into=lambda d: d["x"],
        boundary="test",
        model="m",
    )
    assert unwrap(wobbled) == 1


def test_recovers_first_object_from_trailing_prose(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="llm_wobble"):
        wobbled = parse_with_policy(
            '{"x": 1} and then some prose the model tacked on',
            policies={"x": WobblePolicy(WobbleTolerance.STRICT)},
            into=lambda d: d["x"],
            boundary="test",
            model="m",
        )
    assert unwrap(wobbled) == 1
    assert any(r.fields["field"] == "_envelope" for r in _events(caplog))  # ty: ignore[unresolved-attribute]


def test_non_object_root_raises() -> None:
    with pytest.raises(ParseError, match="expected JSON object"):
        parse_with_policy("[1, 2, 3]", policies={}, into=dict, boundary="test", model="m")


def test_non_policied_fields_are_surfaced() -> None:
    wobbled = parse_with_policy(
        json.dumps({"x": 1, "extra": "kept"}),
        policies={"x": WobblePolicy(WobbleTolerance.STRICT)},
        into=dict,
        boundary="test",
        model="m",
    )
    assert unwrap(wobbled)["extra"] == "kept"


def test_raw_excerpt_bounded_in_log(caplog: pytest.LogCaptureFixture) -> None:
    huge = '{"pad": "' + "z" * 5000 + '"}'
    with caplog.at_level(logging.WARNING, logger="llm_wobble"):
        parse_with_policy(
            huge,
            policies={"x": WobblePolicy(WobbleTolerance.DEFAULT, default=0)},
            into=dict,
            boundary="test",
            model="m",
        )
    events = _events(caplog)
    assert len(events) == 1
    assert len(events[0].fields["raw"]) <= 200  # ty: ignore[unresolved-attribute]


# --------------------------------------------------------------------- #
# Array envelopes
# --------------------------------------------------------------------- #


def test_parse_list_filters_malformed_and_logs_indices(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="llm_wobble"):
        wobbled = parse_list_with_policy(
            '[{"k": 1}, "not-an-object", {"k": 2}, {"drop": true}]',
            item=lambda d: d.get("k"),
            boundary="test",
            model="m",
        )
    assert unwrap(wobbled) == [1, 2]
    assert recovered_fields(wobbled) == ("1", "3")  # index 1 (non-dict) + index 3 (item returned None)
    assert len(_events(caplog)) == 1


def test_parse_list_non_array_root_raises() -> None:
    with pytest.raises(ParseError, match="expected JSON array"):
        parse_list_with_policy('{"not": "a list"}', item=dict, boundary="test", model="m")


def test_first_json_object_extracts_leading_balanced_object() -> None:
    assert _first_json_object('{"a": 1} trailing junk') == '{"a": 1}'
    assert _first_json_object('pre {"a": {"b": 2}} post') == '{"a": {"b": 2}}'
    # brace inside a string value must not close the object early
    assert _first_json_object('{"s": "brace } inside"}') == '{"s": "brace } inside"}'
    assert _first_json_object("no object here") is None


# --------------------------------------------------------------------- #
# Logger injection
# --------------------------------------------------------------------- #


def test_injected_logger_receives_events_not_default(caplog: pytest.LogCaptureFixture) -> None:
    injected = logging.getLogger("llm_wobble_test.injected")
    with caplog.at_level(logging.WARNING):
        emit_wobble(
            boundary="b",
            field="f",
            tolerance=WobbleTolerance.DEFAULT,
            model="m",
            raw_excerpt="raw",
            logger=injected,
        )
    rec = next((r for r in caplog.records if r.getMessage() == "llm_wobble"), None)
    assert rec is not None
    assert rec.name == "llm_wobble_test.injected"  # routed onto the injected channel, not the package default


# --------------------------------------------------------------------- #
# strip_fenced_blocks — the INVERSE of the parse funnel
#
# The funnel keeps the JSON and discards the prose; this keeps the prose and
# discards the JSON. Both need to know what a fence looks like, so the syntax
# lives in one place instead of being re-derived by each caller.
# --------------------------------------------------------------------- #


def test_strip_fenced_blocks_removes_a_labelled_json_block() -> None:
    text = 'The page is a 404.\n\n```next_links\n[{"anchor":"x","url":"https://e.com"}]\n```\n'
    assert strip_fenced_blocks(text) == "The page is a 404."


def test_strip_fenced_blocks_removes_a_json_labelled_block() -> None:
    assert strip_fenced_blocks('answer\n\n```json\n{"a": 1}\n```') == "answer"


def test_strip_fenced_blocks_removes_an_unlabelled_json_block() -> None:
    assert strip_fenced_blocks("answer\n\n```\n[1, 2, 3]\n```") == "answer"


def test_strip_fenced_blocks_keeps_real_code_samples() -> None:
    """`json_only=True` is what makes this safe on answers that quote code."""
    text = "Use this:\n\n```python\nprint('hi')\n```\n\nDone."
    assert strip_fenced_blocks(text) == text.strip()


def test_strip_fenced_blocks_drops_malformed_json_too() -> None:
    """Shape check, not a parse — the payload is discarded either way.

    Requiring valid JSON would silently KEEP the broken blocks, which are exactly
    as unwelcome in prose as the well-formed ones.
    """
    assert strip_fenced_blocks('answer\n\n```json\n[{"a": 1,,,\n```') == "answer"


def test_strip_fenced_blocks_json_only_false_drops_everything() -> None:
    text = "answer\n\n```python\nprint(1)\n```"
    assert strip_fenced_blocks(text, json_only=False) == "answer"


def test_strip_fenced_blocks_handles_multiple_blocks() -> None:
    text = 'a\n\n```json\n{"x":1}\n```\n\nb\n\n```next_links\n[2]\n```\n\nc'
    assert strip_fenced_blocks(text) == "a\n\n\n\nb\n\n\n\nc"


def test_strip_fenced_blocks_is_a_noop_without_fences() -> None:
    assert strip_fenced_blocks("  just prose  ") == "just prose"


def test_strip_fenced_blocks_is_the_inverse_of_the_funnel() -> None:
    """The two halves of the same knowledge, on one payload.

    `parse_with_policy` recovers the JSON; `strip_fenced_blocks` recovers the
    prose. Neither should ever return the other's half.
    """
    payload = 'The answer is 42.\n\n```json\n{"value": 42}\n```'
    prose = strip_fenced_blocks(payload)
    parsed = unwrap(
        parse_with_policy(
            payload,
            policies={"value": WobblePolicy(WobbleTolerance.STRICT)},
            into=lambda d: d,
            boundary="test",
            model="m",
        )
    )
    assert prose == "The answer is 42."
    assert parsed["value"] == 42
