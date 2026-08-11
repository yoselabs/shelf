"""Property-based tests, additive on top of the real-fixture verification lane.

See docs/runbooks/property-based-testing.md. The real-fixture tests are the
package's actual trust anchor (see their own docstring) and stay untouched — this
targets the OK/EMPTY/ROT verdict-selection logic itself, on small synthetic HTML
built from a template, which the fixture lane doesn't isolate (a fixture's
container either matches or it doesn't; it can't cheaply sweep "for any row
count, does OK vs EMPTY get chosen correctly").

Generated text is restricted to a safe alphanumeric+space alphabet so HTML
construction never needs an escaping step of its own — that's a deliberate scope
cut, not an oversight: escaping correctness is selectolax/html's job, not this
package's, and testing it here would be testing someone else's parser.
"""

from __future__ import annotations

from dom_schema import Field, Schema, Yield, extract
from hypothesis import given, settings
from hypothesis import strategies as st

_SAFE_TEXT = st.text(alphabet=st.characters(categories=["L", "N"], max_codepoint=0x2FF), min_size=1, max_size=20)

_SCHEMA = Schema(
    container="div.list",
    row="div.item",
    fields={"title": Field(css=".title")},
)


@given(row_texts=st.lists(_SAFE_TEXT, min_size=1, max_size=15))
@settings(max_examples=100)
def test_property_container_with_n_matching_rows_yields_ok_with_n_rows(row_texts: list[str]) -> None:
    """For any number of rows, each with a non-empty required field, the verdict
    is OK and the row count matches exactly — generalizes any single fixed-N
    fixture test to arbitrary N.
    """
    items = "".join(f'<div class="item"><span class="title">{t}</span></div>' for t in row_texts)
    html = f'<div class="list">{items}</div>'
    result = extract(html, _SCHEMA)
    assert result.verdict is Yield.OK
    assert len(result.rows) == len(row_texts)
    assert bool(result) is True
    assert result.is_rot is False
    assert [r["title"] for r in result.rows] == row_texts


@given(html=st.text(alphabet=st.characters(categories=["L", "N"]), max_size=100))
@settings(max_examples=100)
def test_property_container_never_present_is_always_rot(html: str) -> None:
    """For any HTML that provably never contains the container's class (the
    generated alphabet excludes '<', '"', and '.', so `class="list"` can never
    appear), the verdict is always ROT — never EMPTY, never OK — regardless of
    what else the page contains.
    """
    result = extract(html, _SCHEMA)
    assert result.verdict is Yield.ROT
    assert bool(result) is False
    assert result.is_rot is True
    assert result.rows == ()


@given(filler=_SAFE_TEXT)
@settings(max_examples=50)
def test_property_container_present_with_zero_rows_is_empty_not_rot(filler: str) -> None:
    """The container matching with structurally zero row elements inside is
    EMPTY (a fact about the page), never ROT — for any filler content that
    contains no `.item` element.
    """
    html = f'<div class="list"><p>{filler}</p></div>'
    result = extract(html, _SCHEMA)
    assert result.verdict is Yield.EMPTY
    assert bool(result) is False
    assert result.is_rot is False
    assert result.rows == ()


@given(n_missing=st.integers(min_value=1, max_value=10), n_present=st.integers(min_value=0, max_value=10))
@settings(max_examples=100)
def test_property_rows_missing_every_required_field_count_toward_rot_not_ok(n_missing: int, n_present: int) -> None:
    """A row where the ONLY field is required and absent contributes to `missing`
    and is dropped from `rows` — if ALL rows are like that, the verdict must be
    ROT (the schema found structure but no usable data), never OK with zero
    rows and never silently EMPTY.
    """
    schema = Schema(container="div.list", row="div.item", fields={"title": Field(css=".title", required=True)})
    missing_items = "".join('<div class="item"><span class="other">x</span></div>' for _ in range(n_missing))
    present_items = "".join(f'<div class="item"><span class="title">t{i}</span></div>' for i in range(n_present))
    html = f'<div class="list">{missing_items}{present_items}</div>'
    result = extract(html, schema)
    if n_present == 0:
        assert result.verdict is Yield.ROT
        assert result.missing.get("title") == n_missing
    else:
        assert result.verdict is Yield.OK
        assert len(result.rows) == n_present
        assert result.missing.get("title") == n_missing
