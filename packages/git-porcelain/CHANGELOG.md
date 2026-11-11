# Changelog

## 0.17.0

- `Repo.remote_urls(remote, *, push=False) -> tuple[str, ...]`: every URL, as `git remote get-url --all [--push]`, each rewritten as `remote_url` rewrites one. A fetch reads only the first `url`, but a push goes to every `pushurl` (else to every `url`): a caller that must know where a push goes requires exactly one. FakeRepo lists a second value set with the new `FakeRepo.add_config(key, value)` (`git config --add`).

## 0.16.0

- `Repo.squash(onto, head, message) -> Squashed(sha, tree) | Conflicted(paths)`: one commit whose parent is `onto` and whose tree is `head`'s changes merged onto `onto`, made in Git objects only (`git merge-tree --write-tree`, `git commit-tree --no-gpg-sign`): no checkout, index, HEAD or ref changes, no hook, no signing; author and committer are the repository's identity. FakeRepo merges with `fake_merge.merge_trees` under the same contract scenarios (it has no authors). Needs Git 2.38 or later.
- `Repo.remote_url(remote, *, push=False)`: `push=True` is `git remote get-url --push` (`pushurl`, `pushInsteadOf`, `insteadOf`), in RealRepo and FakeRepo alike.

## 0.15.0

- `Worktree.clean(keep, *, ignored=False, nested=False)`: `nested=True` runs `git clean` with a second `-f`, so nested repositories (a directory holding its own `.git`, such as one inside an ignored `.venv/`) go too; `ignored=True, nested=True` is `git clean -ffdx`. Without it nothing changes (git skips them). FakeRepo holds no nested repositories, so the flag changes nothing there.
- `dirty(ignored_under=["."])` lists the ignored files of the whole checkout, in RealRepo and FakeRepo alike (the empty string stays refused by git); a nested repository in an ignored folder is listed as its directory with a trailing `/`.

## 0.14.0

- `RealRepo(..., pins={checkout: git_dir})`: every call in a pinned checkout (the repo's own path and each worktree view opened with that exact path) sets `GIT_DIR` and `GIT_WORK_TREE` from the caller's verified git directory and never reads `<checkout>/.git`, so a pointer swapped or deleted after the caller's check is not followed (no hostile filter or hook runs, no discovery). A call in a checkout with no pin raises `NotARepo` before any git process. `Worktree.health` runs pinned too in a pinned repo. Without `pins`, nothing changes.

## 0.13.0

- `RealRepo(..., ambient=<mapping>)`: a snapshot of the ambient environment taken once, so a call neither scans `os.environ` nor searches `PATH` (30,000 calls: 1.8 s to 0.01 s). Without it each call still reads the process environment as it is then.

## 0.12.1

- A fetch that loses the race to create a ref (git 2.53: `fetching ref <ref> failed: reference already exists`) is a retryable `RefRace`, like the older lock wording.
