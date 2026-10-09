"""slugify — one slug convention, and the collision transliteration fixes.

The length cap and the fallback are the parameters; everything else is fixed.
"""

from __future__ import annotations

import pytest
from any_file import slugify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MCP spec v2", "mcp-spec-v2"),
        ("  hello  world  ", "hello-world"),
        ("C++ & Rust", "c-rust"),
        ("2026-09-13 notes", "2026-09-13-notes"),
        ("v1.2 spec", "v1-2-spec"),  # NOT `v12`: two versions must not collide
        ("Already-A-Slug", "already-a-slug"),
    ],
)
def test_ascii_text_slugs_the_way_it_always_did(text: str, expected: str) -> None:
    """Every slug already on disk has to keep rendering the same. The regex is
    unchanged and the transliterator is the identity on ASCII, so they do."""
    assert slugify(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Проект", "proekt"),
        ("報告書", "baogaoshu"),
        ("Café Münster", "cafe-munster"),
        ("naïve—dash", "naive-dash"),
        ("Ünicode ✨ emoji", "unicode-sparkles-emoji"),  # an emoji has a name, and it is kept
    ],
)
def test_a_non_latin_title_slugs_to_its_transliteration(text: str, expected: str) -> None:
    """This is the defect the consolidation fixed, not a nicety. Collapsing
    `[^a-z0-9]+` over a Cyrillic or CJK title leaves NOTHING, so every such note
    used to land on the fallback — one slug shared by all of them, in a personal
    vault whose author writes in more than one script."""
    assert slugify(text) == expected


@pytest.mark.parametrize("text", ["", "!!!", "   ", "---"])
def test_text_that_survives_as_nothing_takes_the_fallback(text: str) -> None:
    assert slugify(text) == "untitled"
    assert slugify(text, fallback="file") == "file"


def test_the_cap_bounds_the_result_not_the_input() -> None:
    assert slugify("a" * 100) == "a" * 48
    assert slugify("a" * 100, max_length=60) == "a" * 60


def test_a_cut_landing_mid_word_leaves_no_trailing_hyphen() -> None:
    """Truncation happens after collapsing, so the cut can only ever create a
    trailing hyphen — never a leading one."""
    slug = slugify("aaaa bbbb cccc dddd eeee ffff gggg hhhh iiii jjjj", max_length=15)

    assert not slug.endswith("-")
    assert slug == "aaaa-bbbb-cccc"


def test_an_empty_fallback_is_honoured() -> None:
    """A caller appending a hash suffix asks for one: a name that slugs to nothing must
    yield the bare hash, not `-<hash>`."""
    assert slugify("!!!", fallback="") == ""
