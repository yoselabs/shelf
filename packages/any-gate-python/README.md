# any-gate-python

The Python adapter of [any-gate](../any-gate/README.md): which package suites a change reaches in a uv workspace, and the key each suite passed under.

```bash
python -m any_gate_python --plan | python -m any_gate test --receipts .git/gate-receipts.json
python -m any_gate_python --explain      # the pytest paths, with the changed files on stderr
python -m any_gate_python --reach 50     # how many suites each of the last 50 commits reaches
```

A change selects the packages it touches and, through the graph (dependencies, optional dependencies, dependency groups), every package depending
on them. A path the graph cannot see, or a pytest plugin package, selects every package. The lock is read per package through `uv export`, so a
release that only edits `uv.lock` reaches the packages whose resolved set changed, not all of them. When uv or the base tree cannot answer, every
package is selected: never a silent pass.

`--plan` prints `path<TAB>key` per suite. A package suite's key is its fingerprint: its files, its dependencies' files and resolved sets, and the
root pytest and coverage settings. The repo's own tests carry no key and always run.

## Config

The repo's own paths are read from `[tool.any-gate.python]` in the root `pyproject.toml` (see `rules.py`): `no-effect` paths no package test can
see, `repo-tests` (the whole-repo tests that always run), and `gated` tests that run only when an input they read changed. A path entry is a file,
or a directory with a trailing `/`. With no config every path outside `packages/` selects every package.

Stdlib only; shells out to `uv` and `git`.
