"""What a search query asks of a SQLite FTS5 index: words, exact terms, identifier routing.

A query has two kinds of constraint. A **word** is matched the way the FTS index reads
prose — stemmed, case-folded (`rounds` finds `round`). An **exact term** is an
identifier token (`R189`, `2026-09`, `call/2026-08-01`) or a quoted phrase, and is
matched the way `grep -w -i` would: the literal text with a non-alphanumeric (or the
edge of the text) on each side. `R18` therefore does not find `R189`, and `2026-09`
finds `2026-09-14` but not `2026-07`. Letters and digits of every script count, so
`Москва` does not find `Москвач`.

A :class:`Fold` names letters the index reads as one (`ё` as `е`). The caller folds the
index text with :meth:`Fold.sql`, and the same fold drives a query's terms
(:func:`fts_terms`) and an exact term's regex (:func:`boundary_pattern`), so the two
sides cannot disagree.

A query made only of exact terms is **identifier-only**: it has a right answer, so a
caller can skip any fuzzy or semantic tier for it.
"""

# ruff: noqa: RUF002 — the docstrings name Cyrillic letters on purpose: the fold is about them.
from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

#: The FTS5 tokenizer this package's defaults assume: a run of letters and digits is one
#: term, everything else separates, diacritics fold (`café` is `cafe`), and porter stems
#: prose (`rounds` finds `round`). Digits are kept and porter leaves a term ending in one
#: alone, so `r189`, `rs1805009` and `2026` index whole.
DEFAULT_TOKENIZE = "porter unicode61 remove_diacritics 2"

#: A letter or digit of any script; `_` is a separator, as it is to the tokenizer.
_WORD_CHAR = r"[^\W_]"

_PHRASE_RE = re.compile(r'"([^"]*)"')
#: Separators that, inside a token, make it an identifier (`call/2026-08-01`, `a_b`, `e.g`).
_ID_INNER = frozenset("/-_.:")
#: Punctuation a token may carry at its edges without it being part of the token.
_EDGE_PUNCT = "\"'`.,;:!?()[]{}<>"


class FtsQueryError(ValueError):
    """A fold table this package cannot apply on both sides of the index."""


class Fold:
    """Letters read as one: each key is replaced by its value, in the index and in a query.

    ``Fold({"ё": "е", "Ё": "Е"})`` makes `ёлка` and `елка` one term. FTS5's
    ``remove_diacritics`` folds Latin only, so a fold like this is how another script's
    variant letters become one term. Changing a fold changes what an index holds: an index
    built under another fold must be rebuilt.
    """

    def __init__(self, table: Mapping[str, str] | None = None) -> None:
        table = dict(table or {})
        for src, dst in table.items():
            if len(src) != 1 or len(dst) != 1 or "'" in (src, dst):
                msg = f"a fold maps one letter to one letter, not a quote: {src!r} -> {dst!r}"
                raise FtsQueryError(msg)
        self._table = table
        self._translate = str.maketrans(table)
        groups: dict[str, set[str]] = {}
        for src, dst in table.items():
            groups.setdefault(dst.lower(), {dst.lower()}).add(src.lower())
        self._classes: dict[str, str] = {}
        for members in groups.values():
            cls = "[" + "".join(re.escape(ch) for ch in sorted(members)) + "]"
            for ch in members:
                self._classes[ch] = cls
                self._classes[ch.upper()] = cls

    @property
    def table(self) -> dict[str, str]:
        return dict(self._table)

    def text(self, text: str) -> str:
        """``text`` as the index holds it."""
        return text.translate(self._translate)

    def sql(self, expr: str) -> str:
        """The SQL that folds the SQL expression ``expr`` — the index side of :meth:`text`."""
        for src, dst in self._table.items():
            expr = f"replace({expr}, '{src}', '{dst}')"
        return expr

    def literal(self, text: str) -> str:
        """``text`` escaped for a regex, each folded letter matching either spelling."""
        return "".join(self._classes.get(ch) or re.escape(ch) for ch in text)


#: No letters folded.
NO_FOLD = Fold()


@dataclass(frozen=True)
class ParsedQuery:
    words: tuple[str, ...]
    exact: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.words and not self.exact

    @property
    def is_identifier(self) -> bool:
        """Every constraint is exact: no fuzzy tier, no embedding."""
        return not self.words and bool(self.exact)


def is_identifier_token(token: str) -> bool:
    """A token with a digit, or with a `/ - _ . :` between two other characters."""
    if any(ch.isdigit() for ch in token):
        return True
    return any(ch in _ID_INNER for ch in token[1:-1])


def parse(query: str) -> ParsedQuery:
    """Split ``query`` into words and exact terms, in the order they were written."""
    exact: list[str] = []
    words: list[str] = []
    rest = query
    if query.count('"') >= 2:
        exact.extend(p.strip() for p in _PHRASE_RE.findall(query) if p.strip())
        rest = _PHRASE_RE.sub(" ", query)
    for raw in rest.split():
        token = raw.strip(_EDGE_PUNCT)
        if not any(ch.isalnum() for ch in token):
            continue
        (exact if is_identifier_token(token) else words).append(token)
    return ParsedQuery(words=tuple(words), exact=tuple(exact))


def boundary_pattern(term: str, fold: Fold = NO_FOLD) -> str:
    """A case-insensitive Python regex for ``term`` as a whole word, in any script.

    No letter or digit (of any script) may touch either end. Whitespace inside a phrase
    matches any run of whitespace, so a phrase broken across lines still matches; a folded
    letter matches either spelling, as it does in the index.
    """
    body = r"\s+".join(fold.literal(part) for part in term.split())
    return rf"(?i)(?<!{_WORD_CHAR}){body}(?!{_WORD_CHAR})"


def word_start(prefix: str, fold: Fold = NO_FOLD) -> str:
    """A case-insensitive Python regex for a word that begins with ``prefix``, in any script."""
    return rf"(?i)(?<!{_WORD_CHAR}){fold.literal(prefix)}"


class Tokens:
    """FTS5's own tokenizer, run over a few texts: the terms the index files each under.

    A private in-memory database, so it never touches an index file or its locks, and
    a query's terms are cut, case-folded and stripped of diacritics exactly as the
    index's are — no Python copy of the tokenizer to drift from it.
    """

    def __init__(self, tokenize: str) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
        self._conn.execute(f"CREATE VIRTUAL TABLE tok USING fts5(body, tokenize='{tokenize}')")
        self._conn.execute("CREATE VIRTUAL TABLE tok_vocab USING fts5vocab(tok, instance)")
        self._lock = threading.Lock()

    def cut(self, texts: Sequence[str]) -> list[list[str]]:
        """Each text's terms, in order. The texts go in as written: fold them first."""
        out: list[list[str]] = [[] for _ in texts]
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.executemany("INSERT INTO tok(rowid, body) VALUES (?, ?)", list(enumerate(texts)))
                rows = self._conn.execute("SELECT doc, term FROM tok_vocab ORDER BY doc, offset").fetchall()
            finally:
                self._conn.execute("ROLLBACK")
        for doc, term in rows:
            out[doc].append(term)
        return out

    def close(self) -> None:
        self._conn.close()


def unstemmed(tokenize: str) -> str:
    """``tokenize`` without its ``porter`` wrapper: terms as written."""
    return tokenize.removeprefix("porter ")


@cache
def _unstemmed(tokenize: str) -> Tokens:
    return Tokens(unstemmed(tokenize))


def fts_terms(text: str, stopwords: Collection[str], *, fold: Fold = NO_FOLD, tokenize: str = DEFAULT_TOKENIZE) -> list[str]:
    """The terms an FTS index tokenized by ``tokenize`` makes of ``text`` (before stemming).

    ``text`` is folded first, as the index folds its own. ``stopwords`` are dropped: an
    index can keep them while a query drops them, so `notes about the budget` asks for
    `notes` and `budget` only.
    """
    return [t for t in _unstemmed(tokenize).cut([fold.text(text)])[0] if t not in stopwords]


__all__ = [
    "DEFAULT_TOKENIZE",
    "NO_FOLD",
    "Fold",
    "FtsQueryError",
    "ParsedQuery",
    "Tokens",
    "boundary_pattern",
    "fts_terms",
    "is_identifier_token",
    "parse",
    "unstemmed",
    "word_start",
]
