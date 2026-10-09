"""Brace path templates both ways. Moved from a2kay (core/file_pattern.py).

The example paths are a2kay vault layouts: projects, decisions inside a project, journals.
"""

from __future__ import annotations

from typing import Any

import path_pattern as fp
import pytest


@pytest.mark.parametrize(
    ("pattern", "args", "expected"),
    [
        ("Projects/{id}-{slug}/README.md", {"id": "136", "slug": "a2kay"}, "Projects/136-a2kay/README.md"),
        ("Researches/{id}-{slug}/readme.md", {"id": "139", "slug": "test"}, "Researches/139-test/readme.md"),
        (
            "{parent_path}/decisions/{n:04}-{slug}.md",
            {"parent_path": "Projects/136-a2kay", "n": 14, "slug": "x"},
            "Projects/136-a2kay/decisions/0014-x.md",
        ),
        ("Profile/me.md", {}, "Profile/me.md"),
        ("People/{slug}.md", {"slug": "morgan"}, "People/morgan.md"),
    ],
)
def test_resolve_table(pattern: str, args: dict[str, Any], expected: str) -> None:
    assert fp.resolve(pattern, args) == expected


def test_resolve_missing_arg_raises() -> None:
    with pytest.raises(fp.PatternError, match="missing placeholder"):
        fp.resolve("Projects/{id}-{slug}/README.md", {"id": "1"})


def test_resolve_width_requires_int() -> None:
    with pytest.raises(fp.PatternError, match="integer"):
        fp.resolve("{parent_path}/decisions/{n:04}-{slug}.md", {"parent_path": "x", "n": "not-int", "slug": "y"})


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("Projects/{id}-{slug}/README.md", "Projects/136-a2kay/README.md", {"id": "136", "slug": "a2kay"}),
        ("Researches/{id}-{slug}/readme.md", "Researches/139-test/readme.md", {"id": "139", "slug": "test"}),
        ("People/{slug}.md", "People/morgan.md", {"slug": "morgan"}),
        ("Profile/me.md", "Profile/me.md", {}),
        (
            "{parent_path}/decisions/{n:04}-{slug}.md",
            "Projects/136-a2kay/decisions/0014-x.md",
            {"parent_path": "Projects/136-a2kay", "n": "0014", "slug": "x"},
        ),
    ],
)
def test_reverse_match(pattern: str, path: str, expected: dict[str, str]) -> None:
    assert fp.reverse_match(pattern, path) == expected


def test_reverse_match_handles_nested_journal_yyyy_mm_segments() -> None:
    # journal-kind D-B: {yyyy}/{mm} are ordinary placeholder names, so the two extra
    # nested literal/placeholder segments round-trip exactly like the existing
    # {parent_path}/decisions/{n:04}-{slug}.md nesting — no core engine change needed.
    pattern = "{parent_path}/journal/{yyyy}/{mm}/{slug}.md"
    path = "Projects/136-a2kay/journal/2026/07/2026-07-14.md"
    assert fp.reverse_match(pattern, path) == {
        "parent_path": "Projects/136-a2kay",
        "yyyy": "2026",
        "mm": "07",
        "slug": "2026-07-14",
    }
    # Forward resolve is the exact inverse.
    assert fp.resolve(pattern, {"parent_path": "Projects/136-a2kay", "yyyy": "2026", "mm": "07", "slug": "2026-07-14"}) == path


def test_reverse_match_returns_none_on_mismatch() -> None:
    assert fp.reverse_match("Projects/{id}-{slug}/README.md", "Notes/something.md") is None


def test_reverse_match_slug_does_not_cross_separator() -> None:
    # Without separator protection, `{slug}.md` would greedily match `foo/bar.md`.
    assert fp.reverse_match("People/{slug}.md", "People/foo/bar.md") is None


def test_placeholders_listing() -> None:
    names = fp.placeholders("{parent_path}/decisions/{n:04}-{slug}.md")
    assert names == ["parent_path", "n", "slug"]


def test_reverse_width_pattern_enforces_digit_count() -> None:
    # 3-digit `n` should not match a 4-digit pattern.
    assert fp.reverse_match("X/{n:04}-{slug}.md", "X/123-foo.md") is None
    assert fp.reverse_match("X/{n:04}-{slug}.md", "X/0123-foo.md") == {"n": "0123", "slug": "foo"}


def test_reverse_match_multi_hyphen_slug_does_not_bleed_into_id() -> None:
    # Bug A: greedy `{id}` used to eat up to the LAST hyphen. Lazy capture takes
    # the minimal leading token; the slug absorbs the remaining hyphenated tail.
    assert fp.reverse_match("Projects/{id}-{slug}/README.md", "Projects/140-agent-bootstrap-and-discovery/README.md") == {
        "id": "140",
        "slug": "agent-bootstrap-and-discovery",
    }
    # Single-token name still parses identically.
    assert fp.reverse_match("Projects/{id}-{slug}/README.md", "Projects/136-a2kay/README.md") == {
        "id": "136",
        "slug": "a2kay",
    }


def test_reverse_match_is_case_insensitive_on_literals() -> None:
    # Bug D: a foreign vault's lowercase `readme.md` must match a `README.md`
    # pattern so the entity indexes instead of being dropped as an orphan.
    assert fp.reverse_match("People/{id}-{slug}/README.md", "People/114-gregg/readme.md") == {
        "id": "114",
        "slug": "gregg",
    }


def test_resolve_keeps_canonical_casing() -> None:
    # Forward resolve is unchanged by the case-insensitive read path.
    assert fp.resolve("People/{id}-{slug}/README.md", {"id": "114", "slug": "gregg"}) == "People/114-gregg/README.md"


def test_the_compiled_pattern_is_reused_across_calls() -> None:
    """`reverse_match` compiles the pattern, and it runs once per file per candidate
    type on every index pass (a2kay-z4c).

    A program's patterns are a small fixed set; recompiling per call made a2kay's vault
    indexing O(files x types) regex constructions.
    """
    fp._to_regex.cache_clear()
    pattern = "Projects/{id}-{slug}/README.md"
    for i in range(50):
        fp.reverse_match(pattern, f"Projects/{i}-x/README.md")

    info = fp._to_regex.cache_info()
    assert info.currsize == 1, "one pattern, one compiled regex"
    assert info.misses == 1
    assert info.hits == 49


def test_a_width_is_a_minimum_both_ways() -> None:
    """`{id:03}` writes at least three digits, so it reads at least three: project 1000
    must read back once the ids outgrow the width. Fewer digits still do not match —
    that is what keeps a loose pattern like `{parent_path}/{n:04}-{slug}.md` from
    claiming every `12-notes.md` in a project."""
    pattern = "Projects/{id:03}-{slug}/README.md"
    assert fp.resolve(pattern, {"id": 85, "slug": "acme"}) == "Projects/085-acme/README.md"
    assert fp.resolve(pattern, {"id": 1000, "slug": "big"}) == "Projects/1000-big/README.md"
    assert fp.reverse_match(pattern, "Projects/085-acme/README.md") == {"id": "085", "slug": "acme"}
    assert fp.reverse_match(pattern, "Projects/1000-big/README.md") == {"id": "1000", "slug": "big"}
    assert fp.reverse_match(pattern, "Projects/85-acme/README.md") is None


def test_parse_keeps_each_width() -> None:
    assert fp.parse("{parent_path}/{n:04}-{slug}.md") == [
        fp.Placeholder("parent_path", None),
        fp.Placeholder("n", 4),
        fp.Placeholder("slug", None),
    ]


def test_specificity_counts_the_literal_characters() -> None:
    assert fp.pattern_specificity("Profile/me.md") == len("Profile/me.md")
    assert fp.pattern_specificity("{parent_path}/{slug}.md") == len("/.md")
    assert fp.pattern_specificity("Projects/{id}-{slug}/README.md") > fp.pattern_specificity("{parent_path}/{slug}.md")
