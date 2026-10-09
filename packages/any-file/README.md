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
af.slugify("Проект: план v1.2")         # 'proekt-plan-v1-2'
af.secret_pattern("deploy/.env.prod")   # '.env.*' — None for 'token.png'
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
- `slugify(text, max_length=48, fallback="untitled")` transliterates first (anyascii, ISC;
  `python-slugify`'s transliterator is Artistic/GPL-dual), then keeps `[a-z0-9]` runs joined
  by `-`. Without transliteration a Cyrillic or CJK title collapses to nothing, and every
  such name shares the fallback. anyascii is the identity on ASCII, so ASCII slugs are what
  the regex alone gives. The cap bounds the result, and a cut leaves no trailing hyphen.
- `secret_pattern(path)` matches the basename, case-insensitively, against
  `SECRET_NAME_PATTERNS`: files that hold a credential because of what they are (`.env*`,
  `*.pem`, `*.key`, `credentials.json`, `.netrc`, SSH private keys, …), never a name that
  merely mentions a secret (`token.png`). What to do about a match is the caller's policy.
- Errors: `UnsafeNameError` and `PathEscapeError`, both `AnyFileError`, carrying `value`.

Stdlib, plus anyascii for `slugify`.
