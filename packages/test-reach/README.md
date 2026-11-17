# test-reach

Stop guessing which code a test proves. Run named pytest tests in one in-process session and get, per test, the
functions it executed and whether it passed. Coverage is measured around each test's call only, so imports at
collection never count as behaviour. Uses py-symbols to map executed lines to qualified functions.

```python
from pathlib import Path
from test_reach import run, union

reaches = run(Path("."), ["tests/test_fee.py::test_late_fee"])   # import_roots=("src",), exclude=("tests/",)
reaches["tests/test_fee.py::test_late_fee"].functions            # frozenset({("src/app/fee.py", "late_fee")})
union(reaches.values()).passed                                   # every test passed
```

| call | job |
|---|---|
| `run(root, node_ids, *, import_roots=("src",), exclude=("tests/",))` | run each `path::name` once; `{node_id: Reach}`. `import_roots` are put on `sys.path` (repo modules are forgotten before and after, so edits are seen); `exclude` prefixes are dropped from the result |
| `Reach(files, functions, passed)` | repo-relative files and `(file, qualified function)` pairs; `passed` is true when the call (and setup) passed |
| `union(reaches)` | one entry's reach over its tests; passes when there is at least one and all passed |

A node id that does not exist, or whose file is missing, returns not passed with nothing reached; it never stops
the session. `run` runs pytest in the calling process: call it from a tool, not from inside a running test session
that measures coverage itself.
