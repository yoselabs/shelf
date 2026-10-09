# jsonl-log

**Stop caring how an append-only JSON-lines log rotates and reads back.** One line per write,
size rotation that never splits a line, and reads that skip what does not decode.

```python
import jsonl_log as jl

with jl.JsonlLog.open(path, rotate_bytes=5 * 1024 * 1024, keep=5) as log:
    log.append(b'{"verb": "read"}\n')         # bytes, one line; the newline is added if missing
    log.append_json({"verb": "write"})        # compact json.dumps
    for file in log.files():                  # path, path.1, … path.{keep-1}: newest first
        for row in jl.read(file, json.loads): # a line that does not decode is skipped
            ...
    list(log.records(json.loads))             # every file, newest file first

jl.JsonlLog.open(path, read_only=True)        # a reader beside the writer: append writes nothing
```

## Rules

- **Writes.** One `write` + `flush` per line, no `fsync`. The size is counted in process,
  seeded by one `tell` at open. The file is opened in append mode only.
- **Rotation.** Before an append would take the file past `rotate_bytes`, the files shift:
  `.{keep-2}` → `.{keep-1}` (the oldest is dropped), …, the file → `.1`. At most `keep` files
  exist, and a line is never split across two.
- **Reads.** A missing file reads empty; a blank line is skipped; a line the `decode`
  callable refuses with `ValueError` (a torn last line, `json.JSONDecodeError`, a pydantic
  `ValidationError`) is skipped.
- **Errors.** `append` on a closed log raises `LogClosedError`; a line holding a newline
  before its end raises `LineError`. Both are `JsonlLogError`.
- A `read_only` log never opens the file for writing and its `append` returns `False`.

Codec-agnostic: the caller owns what a line means. Stdlib only.
