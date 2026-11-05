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
jl.JsonlLog.open(path, rotate_lock=True)      # rotation (and rewrite) exclusive across processes: path.lock
log.rewrite(lambda line: json.loads(line)["t"] >= cutoff)  # keep what is accepted; returns how many lines went
jl.held(path, rotate_lock=True).append_json(row)  # one open log per path per process; jl.close_held() at exit
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

- **Writes.** One `write` call per line on an `O_APPEND` descriptor, no `fsync`. The kernel
  moves to the end and writes under one lock, so lines from several processes do not interleave
  on a **local** filesystem (APFS, ext4), the case this is tested on. POSIX promises that only
  up to `PIPE_BUF` (512 bytes to 4 KiB, by system); past it the guarantee is that of the local
  filesystem, and **NFS gives none** (`O_APPEND` is emulated client-side there: lines may overlap
  or tear). Do not share a log across hosts. The size is read from the descriptor at each append,
  and a file another process rotated away is reopened. The file is opened in append mode only.
- **Rotation.** Before an append would take the file past `rotate_bytes`, the files shift:
  `.{keep-2}` → `.{keep-1}` (the oldest is dropped), …, the file → `.1`. At most `keep` files
  exist, and a line is never split across two. **Without `rotate_lock`**, two processes rotating
  at the same moment shift twice and drop a file. **With it** (opt-in; `True` is `<path>.lock` for a
  `Path` or `str` path alike, or pass a path; uses `process-lock`) the shift runs under an exclusive lock and the size is
  checked again once the lock is held, so the second rotator finds the file already rotated and
  does nothing. An append never takes the lock, so the common path costs the same.
- **Rewrite.** `rewrite(keep)` (needs `rotate_lock`) keeps the lines `keep(line_bytes)` accepts
  and returns how many it dropped; blank lines go uncounted. The new file is fsynced, keeps the
  old file's mode and is swapped in with `os.replace` (then the directory is fsynced), only when
  a line goes: a crash leaves the old log or the new one, never an empty one. A torn last line is
  kept and closed with a newline. Lines appended meanwhile by a process not holding the lock are
  carried over before the replace and, from the old inode, after it (these land after the lines
  already kept). An `append` also checks that its file was not unlinked by a rewrite right after
  its write and, if so, appends again: **at-least-once** around a rewrite, so a line may then
  appear twice and dedup is the caller's job. If the file is replaced under the append on all four
  attempts (the write and three re-appends) it raises `LineLostError`: the line may not be in the log.
  For exactly-once wrap appends in
  `with log.locked(): log.append(...)`.
- **Held handles.** A `JsonlLog` keeps its descriptor open between appends (an append is one
  `fstat` and one `write`, no open or close; a path stat notices a rotated-away file).
  `held(path, **open_options)` returns the process's one open log for a resolved path; the options
  apply on first sight and asking again with other options raises `ValueError`. A fork child
  closes its inherited copy and opens its own. At most 16 stay open: the least recently used is
  evicted, its descriptor closes but the log stays usable: a thread still holding it reopens the
  descriptor for each append and closes it again before returning, so an evicted log never owns a
  descriptor between appends and nothing leaks (it is slower: one open and close per append). `close_held(path=None)` and `held_count(path=None)`.
  `process-lock` is imported only when `rotate_lock` is used.
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
  before its end raises `LineError`; an append lost to repeated rewrites raises `LineLostError`.
  All are `JsonlLogError`.
- A `read_only` log never opens the file for writing and its `append` returns `False`.

Codec-agnostic: the caller owns what a line means. Stdlib plus `atomic-io` (rewrite) and `process-lock` (imported only with `rotate_lock`).
