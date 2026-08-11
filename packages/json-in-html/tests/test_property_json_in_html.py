"""Property-based tests, additive on top of the example suite.

See docs/runbooks/property-based-testing.md. Targets four pure functions:
`is_json_content_type` / `sniff_json_body` (cheap predicates with a clear
documented contract), `rank_payloads` (a sort — checked as a permutation, not by
re-deriving the sort key), and `extract_json_payloads`'s generic-JSON round-trip
(the one detector whose input shape is simple enough to safely generate).
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st
from json_in_html import JsonPayload, extract_json_payloads, is_json_content_type, rank_payloads, sniff_json_body

_JSON_VALUE = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=10)),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(st.text(alphabet=st.characters(categories=["L"]), min_size=1, max_size=6), children, max_size=3),
    ),
    max_leaves=8,
)
_JSON_OBJECT = st.dictionaries(st.text(alphabet=st.characters(categories=["L"]), min_size=1, max_size=8), _JSON_VALUE, max_size=5)


@given(suffix=st.text(alphabet=st.characters(categories=["L"]), min_size=1, max_size=10))
@settings(max_examples=150)
def test_property_any_application_plus_json_suffix_is_json_content_type(suffix: str) -> None:
    """The docstring's explicit claim: any `application/<x>+json` is JSON-family,
    for any suffix, not just the two hand-picked examples (`vnd.api+json`,
    `ld+json`).
    """
    assert is_json_content_type(f"application/{suffix}+json") is True
    assert is_json_content_type(f"APPLICATION/{suffix}+JSON") is True  # case-insensitive
    assert is_json_content_type(f"application/{suffix}+json; charset=utf-8") is True


@given(suffix=st.text(alphabet=st.characters(categories=["L"]), min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_non_json_family_content_type_is_never_json(suffix: str) -> None:
    """The complement: a type that is neither the two exact matches nor
    `+json`-suffixed is never reported as JSON-family.
    """
    ct = f"application/{suffix}"  # no +json suffix
    if ct.lower() not in ("application/json", "text/json"):
        assert is_json_content_type(ct) is False


@given(value=_JSON_VALUE)
@settings(max_examples=150)
def test_property_json_serialized_bodies_starting_brace_or_bracket_are_sniffed(value: object) -> None:
    """For any JSON-serializable value whose top-level shape is a dict or list
    (so the body starts with `{` or `[`), sniff_json_body recovers it — for
    non-container top-level values (numbers, strings, bare literals) the prefix
    guard correctly says no, which this property checks for too.
    """
    body = json.dumps(value).encode("utf-8")
    starts_container = body[:1] in (b"{", b"[")
    assert sniff_json_body(body) is starts_container


@given(
    sources=st.lists(
        st.sampled_from(["ld_json", "microdata", "next_data", "nuxt_data", "opengraph", "window_var", "generic"]),
        max_size=10,
    ),
    sizes=st.lists(st.integers(min_value=0, max_value=10_000), max_size=10),
)
@settings(max_examples=100)
def test_property_rank_payloads_is_a_permutation(sources: list[str], sizes: list[int]) -> None:
    """rank_payloads reorders; it must never lose, duplicate, or invent a payload
    — checked as a multiset-equality permutation, not by re-deriving the sort key
    (which would just restate the implementation).
    """
    n = min(len(sources), len(sizes))
    payloads = [
        JsonPayload(source=sources[i], data={}, script_id=None, byte_size=sizes[i])  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        for i in range(n)
    ]
    ranked = rank_payloads(payloads)
    assert len(ranked) == len(payloads)
    assert sorted(id(p) for p in ranked) == sorted(id(p) for p in payloads)


@given(payload=_JSON_OBJECT)
@settings(max_examples=100)
def test_property_generic_script_tag_round_trips_through_extraction(payload: dict) -> None:
    """For any JSON-serializable object embedded in a generic
    `<script type="application/json" data-x>` tag, extraction recovers it
    byte-for-byte as `.data` — independent of what the object actually contains.
    """
    body = json.dumps(payload)
    html = f'<html><body><script type="application/json" data-x="1">{body}</script></body></html>'
    results = extract_json_payloads(html)
    generic = [p for p in results if p.source == "generic"]
    assert len(generic) == 1
    assert generic[0].data == payload
