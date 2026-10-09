# fts-query

**Stop caring how a search box's text becomes an FTS5 query.** Split a query into stemmed
words and `grep -w` exact terms, know when it is identifier-only, cut it into exactly the
terms the index holds, and fold variant letters the same way on both sides.

```python
from fts_query import Fold, Tokens, boundary_pattern, fts_terms, parse, word_start

YO = Fold({"ё": "е", "Ё": "Е"})                 # optional: letters read as one

# index side: fold the text before FTS5 sees it
f"CREATE VIEW src AS SELECT rowid, {YO.sql('body')} AS body FROM docs"

q = parse('"Robin Vale" Contoso R189, pricing?')
q.words, q.exact, q.is_identifier                # ('Contoso', 'pricing'), ('Robin Vale', 'R189'), False

boundary_pattern("R189", YO)                     # regex: R189 but not R1890 or заявкаR189
word_start("ёл", YO)                             # regex: a word beginning with ёл/ел
fts_terms("notes about the budget", STOP, fold=YO)  # ['notes', 'budget'], cut by FTS5 itself
Tokens("porter unicode61").cut(["rounds"])       # [['round']]: run the index's own tokenizer
```

## What this package knows

- **Words and exact terms are two kinds of constraint.** A word is matched as the index reads
  prose: stemmed, case-folded. A token with a digit or an inner `/ - _ . :` (`R189`,
  `2026-09`, `call/2026-08-01`, `a_b`) and a quoted phrase are exact: matched like
  `grep -w -i`, so `R18` misses `R189` and `2026-09` finds `2026-09-14`. A query of only
  exact terms is identifier-only: it has a right answer, so a caller can skip fuzzy and
  semantic tiers.
- **A word boundary is any script's letter or digit**, not `[a-z0-9]`: `Москва` does not find
  `Москвач`. `_` separates, as it does to `unicode61`. Whitespace inside a phrase matches a
  line break.
- **Query terms come from FTS5, never from a Python copy of its tokenizer.** `Tokens` runs the
  tokenizer over a private in-memory database, so a query is cut, case-folded and stripped of
  diacritics exactly as the index was.
- **One fold, three places.** `remove_diacritics` folds Latin only. A `Fold` folds other
  letters: `Fold.sql` on the index side, and the same table drives `fts_terms` and the
  exact-term regex, so the two sides cannot disagree. A fold that is not one letter to one
  letter, or that contains a quote, raises `FtsQueryError`.

## Sharp edges

- Changing a fold or the tokenizer changes what an index holds: rebuild it. Put both in the
  index's built marker.
- `fts_terms` drops `stopwords` only from the query; the index may keep them.
- Stdlib only (`sqlite3` with FTS5).
