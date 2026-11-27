# any-gate-python

The Python adapter of [any-gate](../any-gate/README.md): which package suites a change reaches in a uv workspace, and the key each suite passed under.

```bash
python -m any_gate_python plan --plan | python -m any_gate test -- python -m any_gate_python run
python -m any_gate_python plan --explain      # the pytest paths, with the changed files on stderr
python -m any_gate_python plan --reach 50     # how many suites each of the last 50 commits reaches
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

`[tool.any-gate.python.reads]` maps a root file (an fnmatch glob, `*` crosses `/`) to the packages whose tests read it: a change to it selects those
packages and their dependents, and each of them keys its passes on the file's content. An empty list says no suite reads it. A root path in neither
`no-effect` nor `reads` still selects every package. The map is a claim, held by `reads_audit.audit(repo)` (the shelf runs it as
`tests/test_root_reads_are_mapped.py`): it fails when a package's tests name a mapped file (or a folder holding one) the package is not mapped for, when
the root conftest or a plugin it loads names one, or when a test finds the repo root through `parents[3]` and its package is mapped for no file. It is a
static scan: a path built at run time, a constant defined in another module, and `src` code the tests point at the real repo are not seen.

## The runner

`run [--workers auto|N] [--wall S] [--idle S] [--nice N] [--pytest-args "ARGS"] PATH...` is the runner `any-gate test` calls: pytest in stages, parallel
(xdist, sized to the tests and the box), then `serial` alone, then `quarantine` (a failing quarantined test is reported, never blocks). A stage
selects its lane through a pytest plugin, not `-m`, so the repo's own `-m` default stays in force. A stage over the wall or idle limit has its
whole process tree stopped. The repo declares the `serial` and `quarantine` markers itself.

Selection is stdlib only and shells out to `uv` and `git`; the runner uses `any-gate` (box sizing) and `stream-proc` (the limits).
