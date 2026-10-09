# any-file

**Stop caring what a file's name and bytes say.** The checks a program needs before it
writes a file someone else named, and the media type it should record, the same on every
host.

```python
import any_file as af

af.safe_name("Résumé.pdf")             # bare basename, NFC: one spelling per name
af.safe_name("../evil")                # UnsafeNameError
af.resolve_within(root, "sub/x.pdf")   # resolved path, inside root
af.resolve_within(root, "../../etc")   # PathEscapeError
af.looks_binary(data)                  # a NUL in the first 8 KiB
af.name_collision(["Report.pdf"], "report.pdf")  # 'Report.pdf': one file on macOS, two in git
af.media_type("budget.xlsx")           # 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
af.media_type("x.bin", declared="image/png")     # the caller's word wins
af.media_type("noext")                 # 'application/octet-stream'
af.is_text_media("application/json")   # True: text/*, JSON, NDJSON
```

## Rules

- `safe_name` refuses an empty name, `.`, `..` and any name holding a separator (`/`, `\`,
  `os.sep`, `os.altsep`), rather than quietly taking a basename: a caller who meant to
  write elsewhere is refused loudly. It returns the NFC form (macOS hands back decomposed
  accents; git and Linux compare bytes).
- `resolve_within(root, ref)` resolves `ref` (relative or absolute, symlinks followed)
  and refuses anything that lands outside the resolved `root`.
- `name_collision(existing, name)` names the existing entry equal to `name` only after
  case folding and NFC; an exact match is not a collision.
- `media_type(name, declared=None)` reads **a table this package owns**, never the
  host's `/etc/mime.types`: a slim container image has none, and `.xlsx` or `.docx` came
  back unknown there. The table is Python's built-in one plus the office (OOXML, ODF),
  JSON-lines, YAML, TOML and common audio, image and video types, and every allow-worthy extension a common `mime.types` names (`.mpga`, `.wmv`, `.psd`, …) plus `.amr`. A compression suffix is
  an encoding: `genome.vcf.gz` is `text/x-vcard`.
- Errors: `UnsafeNameError` and `PathEscapeError`, both `AnyFileError`, carrying `value`.

Stdlib only.
