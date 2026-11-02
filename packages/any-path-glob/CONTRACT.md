# Repo-relative glob matching

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

`Glob(pattern: str)` retains the pattern and its compiled regex immutably.
`matches(path: str) -> bool` follows the README dialect and matches the whole path.
Unclosed opening braces raise `GlobError`; all patterns accepted by the original
compiler retain their matching behavior. Compilation is cached across instances.

`GlobSet(globs: Iterable[str | Glob])` owns an ordered collection deduplicated by
pattern. `matches` and membership match any glob; `first` returns the first
matching Glob or None; `filter` preserves input order and duplicates. Iteration
yields the unique globs and length counts them. No consumer app is imported.

Executable acceptance: `tests/test_glob.py` (80 differential table pairs, seeded
random sweep, dialect and construction rules), `tests/test_glob_set.py` (ordered
selection), and `tests/test_boundary_any_path_glob.py` (consumer boundary).
