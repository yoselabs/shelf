# Changelog

## 0.14.0

- `RealRepo(..., pins={checkout: git_dir})`: every call in a pinned checkout (the repo's own path and each worktree view opened with that exact path) sets `GIT_DIR` and `GIT_WORK_TREE` from the caller's verified git directory and never reads `<checkout>/.git`, so a pointer swapped or deleted after the caller's check is not followed (no hostile filter or hook runs, no discovery). A call in a checkout with no pin raises `NotARepo` before any git process. `Worktree.health` runs pinned too in a pinned repo. Without `pins`, nothing changes.

## 0.13.0

- `RealRepo(..., ambient=<mapping>)`: a snapshot of the ambient environment taken once, so a call neither scans `os.environ` nor searches `PATH` (30,000 calls: 1.8 s to 0.01 s). Without it each call still reads the process environment as it is then.

## 0.12.1

- A fetch that loses the race to create a ref (git 2.53: `fetching ref <ref> failed: reference already exists`) is a retryable `RefRace`, like the older lock wording.
