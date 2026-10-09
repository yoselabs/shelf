"""Query parsing: words, exact terms, identifier routing, and the index tokenizer's terms.

Moved from a2kay (services/search/match.py), which folds `ё` to `е`; the fold tests pass
that table explicitly.
"""

# ruff: noqa: RUF001, RUF002 — any-script word boundaries need Cyrillic, Greek and long-s test data.
from __future__ import annotations

import re
import sqlite3

import pytest
from fts_query import (
    DEFAULT_TOKENIZE,
    NO_FOLD,
    Fold,
    FtsQueryError,
    boundary_pattern,
    fts_terms,
    is_identifier_token,
    parse,
    unstemmed,
    word_start,
)

YO = Fold({"\u0451": "\u0435", "\u0401": "\u0415"})  # small and capital yo to ie


@pytest.mark.parametrize(
    "token",
    ["R189", "2026-09", "rs1805009", "call/2026-08-01", "C22", "v2", "a_b", "e.g", "host:port"],
)
def test_identifier_tokens(token: str) -> None:
    assert is_identifier_token(token)


@pytest.mark.parametrize("token", ["Fabrikam", "rounds", "robin's", "integration"])
def test_plain_words_are_not_identifiers(token: str) -> None:
    assert not is_identifier_token(token)


def test_parse_splits_words_ids_and_phrases() -> None:
    q = parse('"Robin Vale" Contoso R189, pricing?')
    assert q.words == ("Contoso", "pricing")
    assert q.exact == ("Robin Vale", "R189")
    assert q.is_identifier is False


def test_identifier_only_query_routes_exact() -> None:
    assert parse("R189").is_identifier is True
    assert parse("2026-09 C22").is_identifier is True
    assert parse('"round 12"').is_identifier is True  # an all-quoted query is exact too


def test_a_word_makes_the_query_not_identifier_only() -> None:
    assert parse("R189 agent").is_identifier is False


def test_empty_and_punctuation_only_queries_parse_to_nothing() -> None:
    assert parse("").is_empty
    assert parse(' - , "" ').is_empty


def test_unclosed_quote_is_a_word_boundary_not_a_phrase() -> None:
    q = parse('"Robin Vale')
    assert q.words == ("Robin", "Vale")
    assert q.exact == ()


@pytest.mark.parametrize(
    ("term", "text", "hit"),
    [
        ("R189", "see R189 notes", True),
        ("R189", "see r189.", True),
        ("R18", "see R189 notes", False),
        ("rs180", "rs1805009 AG", False),
        ("2026-09", "drawn 2026-09-14", True),  # grep -w: a prefix date matches a full date
        ("2026-09", "drawn 2026-07-14", False),
        ("Robin Vale", "with Robin\n  Vale today", True),
        ("round 12", "round twelve", False),
        ("round 12", "Round 12 of the survey", True),
        ("R189", "id_R189_x", True),  # `_` separates, as it does in the index
    ],
)
def test_boundary_pattern_is_grep_w(term: str, text: str, hit: bool) -> None:
    assert bool(re.search(boundary_pattern(term), text)) is hit


@pytest.mark.parametrize(
    ("term", "text", "hit"),
    [
        ("Москва", "в Москвач уехал", False),
        ("Москва", "Москва, 2026", True),
        ("Москва", "Москва_2", True),
        ("Москва", "в Москве", False),
        ("москва", "Город МОСКВА.", True),
        ("café", "un café noir", True),
        ("café", "cafés", False),
        ("Ελλάδα", "Ελλάδας", False),
        ("Ελλάδα", "η Ελλάδα σήμερα", True),
        ("R189", "заявкаR189", False),
        ("2026-09", "срок 2026-09-14", True),
        ("Анна Берг", "встреча: Анна\n  Берг, вторник", True),
    ],
)
def test_boundary_pattern_is_grep_w_in_any_script(term: str, text: str, hit: bool) -> None:
    """Letters and digits of every script are word characters, not only `a-z0-9`."""
    assert bool(re.search(boundary_pattern(term), text)) is hit


@pytest.mark.parametrize(
    ("term", "text"),
    [("ёлка", "ёлка"), ("ёлка", "елка"), ("елка", "Ёлка"), ("Ёж", "ежи и еж"), ("ещё раз", "еще раз")],
)
def test_boundary_pattern_reads_yo_as_ye(term: str, text: str) -> None:
    assert re.search(boundary_pattern(term, YO), text)


def test_fts_terms_fold_yo_and_keep_short_i() -> None:
    """`ё` is `е` on both sides; `й` is its own letter, as the index tokenizer keeps it."""
    assert fts_terms("Ёлка у моей двери, йод ещё", (), fold=YO) == ["елка", "у", "моей", "двери", "йод", "еще"]


def test_fts_terms_mirror_the_index_tokenizer() -> None:
    stop = frozenset({"with", "the", "s"})
    assert fts_terms("call/2026-08-01", stop) == ["call", "2026", "08", "01"]
    assert fts_terms("Robin's call with Acme", stop) == ["robin", "call", "acme"]
    assert fts_terms("the", stop) == []


@pytest.mark.parametrize(
    "text",
    [
        "R189 rs1805009 2026-09-14 call/2026-08-01 a_b e.g",
        "Café naïve résumé x-ray v2.0",
        "Ёлка мой йод ещё Ελλάδα ά İstanbul ǅ ſ",
    ],
)
def test_fts_terms_cut_text_where_the_fts5_tokenizer_does(text: str) -> None:
    """Before stemming, a query's terms are the index's terms (folded the way the index
    folds its text): ids and dates stay whole, accents fold, `ё` is `е`, `й` stays."""
    con = sqlite3.connect(":memory:")
    con.execute(f"CREATE VIRTUAL TABLE f USING fts5(b, tokenize='{unstemmed(DEFAULT_TOKENIZE)}')")
    con.execute("CREATE VIRTUAL TABLE v USING fts5vocab(f, 'instance')")
    con.execute(f"INSERT INTO f(b) SELECT {YO.sql('?')}", [text])
    assert [r[0] for r in con.execute("SELECT term FROM v ORDER BY offset")] == fts_terms(text, (), fold=YO)


def test_without_a_fold_yo_and_ye_are_two_letters() -> None:
    assert not re.search(boundary_pattern("ёлка"), "елка")
    assert fts_terms("ёлка", ()) == ["ёлка"]
    assert NO_FOLD.text("ёлка") == "ёлка"
    assert NO_FOLD.sql("body") == "body"


def test_word_start_folds_and_respects_the_left_boundary() -> None:
    assert re.search(word_start("ёл", YO), "Елки")
    assert not re.search(word_start("лка", YO), "елка")


def test_a_fold_names_its_sql_and_its_table() -> None:
    assert YO.sql("body") == "replace(replace(body, 'ё', 'е'), 'Ё', 'Е')"
    assert YO.table == {"ё": "е", "Ё": "Е"}


@pytest.mark.parametrize("table", [{"ab": "a"}, {"a": ""}, {"'": "a"}])
def test_a_fold_that_cannot_hold_on_both_sides_is_refused(table: dict[str, str]) -> None:
    with pytest.raises(FtsQueryError):
        Fold(table)
