# any-frontmatter

**Stop caring how a markdown file's YAML frontmatter is read, written and versioned.**

```python
from any_frontmatter import read, write, write_checked, compute_version, opt_str

doc = read(path)                                  # Document(frontmatter, body), comments kept
version = compute_version(doc)                    # same for a reorder or CRLF; changes with content
write_checked(path, merge=lambda cur: cur.with_frontmatter({**cur.frontmatter, "status": "done"}),
              expected=version)                   # StaleVersionError if someone wrote in between
opt_str(doc.frontmatter.get("title"))             # None for nothing written, never an exception
```

## What this package knows

1. **The author's comments live in ruamel's map, not in a dict.** `parse` returns the
   round-trip map un-copied; `dict(parsed)` deletes every comment on the next write.
   `Document.with_frontmatter` replaces the whole mapping while keeping them (extra
   `merge`, which is yaml-merge).
2. **One error for every malformed file.** An unclosed fence, a non-mapping and YAML the
   parser cannot read are all `FrontmatterError`, the parser's position kept and its error
   chained. A walk that must survive one bad file catches one type.
3. **A value with two spaces in a row is quoted.** Wrapped as a plain scalar, its line
   break reads back as one space. The rule is on a private representer subclass, so other
   ruamel dumps in the process are untouched.
4. **A failed dump must not poison the next.** ruamel's emitter keeps its state after a
   value it cannot represent, and the next dump on the same instance writes an empty
   mapping. Each dump uses a fresh instance.
5. **Writes are atomic** — temp file beside the target, fsync, rename.
6. **A version ignores layout.** SHA-256 over key-sorted JSON frontmatter and a body with
   LF line endings and one trailing newline.
7. **A checked write re-checks after the rename.** A writer that lands between the read and
   the rename is retried against the fresh file, up to `retries`, and never overwritten.
8. **Reads of untyped values never raise.** `opt_str`, `str_seq`: nothing written (`None`,
   `""`, `[]`, `{}` — lean-wire's `is_empty`) is `None`/`()`; `0` and `False` are present.

## Surface

| | |
|---|---|
| `Document(frontmatter, body)` · `.with_frontmatter(fm, body=None)` | the value; comment-keeping replace (extra `merge`) |
| `parse(text)` · `read(path)` · `dump(doc)` · `write(path, doc)` | `FrontmatterError` on malformed input |
| `canonicalize(doc)` · `version_of(fm, body)` · `compute_version(doc)` · `version_of_file(path)` | content-hash versions |
| `write_checked(path, merge=, expected=None, retries=2)` → `WriteOutcome(path, version)` | `StaleVersionError(path, expected, actual)` |
| `check_version(path, expected)` | the same refusal for a delete or a move |
| `round_trip_yaml()` | a fresh ruamel instance configured the same way, for other YAML files |
| `opt_str(v)` · `str_seq(v)` · `written_nothing(v)` | total reads |
