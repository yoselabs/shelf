# Test reach

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `run(root, node_ids, *, import_roots=("src",), exclude=("tests/",)) -> dict[str, Reach]`: one in-process pytest session over the files of `node_ids`; only the named tests run, each once; the repository's conftest and fixtures work. Coverage starts and stops around each test's call phase, so collection-time imports and fixtures' setup are not counted.
- `Reach(files, functions, passed)`: repo-relative POSIX files and `(file, qualified function)` pairs (py-symbols names) under `root`, minus the `exclude` prefixes; `passed` is true when the test's call and any setup or teardown passed.
- A missing node id or file yields `Reach(frozenset(), frozenset(), False)`. No node ids yields `{}`.
- `import_roots` are prepended to `sys.path` for the run, and modules loaded from under `root` are dropped before and after, so edited sources are re-read.
- `union(reaches) -> Reach`: set union; passed only when non-empty and all passed.

No consumer app is imported. Executable acceptance: `tests/`.
