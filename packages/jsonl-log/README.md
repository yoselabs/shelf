# jsonl-log

**Stop caring how an append-only JSON-lines log rotates, ages out and reads back.** One line per
write (safe across processes), size and age retention, reads that skip what does not decode, and
a byte-cursor reader that follows a live file.

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

jl.JsonlLog.open(path, max_age=7 * 86400)     # rotated files untouched for 7 days are deleted
log.append_at(b'{"verb": "read"}')            # like append, returns the line's byte offset
jl.expire(Path("runs").glob("*.jsonl"), 7 * 86400)  # the same age rule for any files

# Follow a live file by byte cursor (what task-loop's contracts/jsonl.py does):
tail = jl.Jsonl(path)                         # objects only; a line that is not one is skipped
offset = tail.append({"kind": "start"})       # writer: one write call, O_APPEND, offset returned
entries, cursor = tail.read_from(0)           # Entry(start, end, data) list + the cursor after them
entries, cursor = tail.read_from(cursor)      # later: only what is new; a torn last line waits
tail.tail(20)                                 # the last 20 complete entries, oldest first
jl.read_from(path, decode, cursor)            # the same with your own decode(bytes) -> T
```

## Rules

- **Writes.** One `write` call per line on an `O_APPEND` descriptor, no `fsync`: processes
  appending to one file never interleave bytes, however long the line. The size is read from
  the descriptor at each append, and a file another process rotated away is reopened. The file
  is opened in append mode only.
- **Rotation.** Before an append would take the file past `rotate_bytes`, the files shift:
  `.{keep-2}` → `.{keep-1}` (the oldest is dropped), …, the file → `.1`. At most `keep` files
  exist, and a line is never split across two. Two processes rotating at the same moment may
  drop one extra file: appends are coordinated, rotation is not.
- **Retention.** With `max_age` (seconds) a rotated file not written to for that long is deleted,
  at open, at each rotation and on `prune()`. `expire(paths, max_age)` applies the rule to any files.
- **Cursor.** `read_from(path, decode, offset, limit)` returns `Entry(start, end, data)` and the
  cursor after them. A last line without its newline is still being written: it is not returned
  and the cursor stays at its start, so the next read returns it whole. A complete line the
  decoder refuses with `ValueError` is skipped and passed. An offset past the end of the file
  (truncated, replaced) restarts at 0. `tail(path, decode, n, before)` takes the last `n`.
- **Reads.** A missing file reads empty; a blank line is skipped; a line the `decode`
  callable refuses with `ValueError` (a torn last line, `json.JSONDecodeError`, a pydantic
  `ValidationError`) is skipped.
- **Errors.** `append` on a closed log raises `LogClosedError`; a line holding a newline
  before its end raises `LineError`. Both are `JsonlLogError`.
- A `read_only` log never opens the file for writing and its `append` returns `False`.

Codec-agnostic: the caller owns what a line means. Stdlib only.
