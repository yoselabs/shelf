# any-recorded-fixture

Record real model-call exchanges per case and replay them against a text golden. Standard library only; Python 3.12+.

```python
from pathlib import Path
from any_recorded_fixture import cases, golden, record, scrub, update_requested

root = Path("fixtures")
record(root, "chat", "hello", {"request.json": {"prompt": "hello"}}, {"model": "example"},
       text={"input.txt": "hello\n"})
for case in cases(root):
    golden(case.dir / "input.txt", scrub("hello\n", wt="/tmp/work"), update=update_requested())
```

## Rules

- Each `<root>/<group>/<case>/` needs `meta.json`; discovery sorts groups, then cases. A missing root is empty.
- `Case(group, case, dir, meta)` holds the directory and metadata dictionary.
- `read_json(path)` and `write_json(path, obj)` use UTF-8; writes use indent=1 and a trailing newline.
- `record` takes complete filenames, creates the case directory, and writes JSON, optional text, then metadata.
  Existing named files are replaced; other files remain. Callers own filenames and concurrency.
- `golden` compares exact text and raises `GoldenMismatchError(AssertionError)` with a unified diff on a mismatch
  or missing file. `update=True` writes the actual text instead; its parent directory must exist.
- `update_requested` reads `UPDATE_GOLDEN` by default: unset, empty and `0` are false; every other value is true.
- `scrub(text, **placeholders)` replaces nonempty values longest first with `<KEY>` tokens.
