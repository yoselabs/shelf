# Changelog

## 0.21.0

A merge of one commit into a checkout that stops before its commit, so a caller can resolve conflicts in the working files and finish it itself (the checked commit X merged with a newer main O: clean changes staged, conflicting files as markers). Real and fake under one contract; no operation writes a ref.

- `Worktree.start_merge(rev) -> MergeStarted(merge_head, conflicts) | UpToDate`: `git merge --no-ff --no-commit --no-verify`. HEAD, the branch and every ref stay put; `conflicts` names the paths left with markers (empty: clean, waiting for `finish_merge`); `UpToDate` when `rev` is already in HEAD's history. `ValueError` on tracked changes, a paused rebase or a merge already under way; `MissingRevision` for an unknown `rev`.
- `Worktree.merging() -> bool`: a stopped merge waits.
- `Worktree.finish_merge(message) -> Sha`: one commit of the index with parents HEAD and the merged commit, the repository's identity, hooks skipped; HEAD moves only (a detached checkout moves, a branch checkout moves its branch). Paths the caller resolved must be staged with `stage`; `UnmergedPaths` while conflict entries remain, nothing committed. `ValueError` with no merge under way.
- `Worktree.abort_merge()`: HEAD, index and files back to before `start_merge`; nothing to do when no merge is under way.
- New result `MergeStarted`. FakeRepo merges with `fake_merge.merge_trees` (the text merge `squash` and `rebase_onto` use).

## 0.20.0

Ignore rules that belong to one checkout, and a park that keeps what is ignored there (so a slot saved with `capture` and parked at its base stays clean to plain `git status`, with its ignored files untouched, even when the saved work had changed the ignore rules):

- `Worktree.exclude(patterns)`: append the missing patterns to this checkout's own ignore rules. The repository's `info/exclude` and every other checkout stay as they are; `dirty`, `capture`, `record`, `clean` and a plain `git status` in this checkout honor them. Real: a `worktree-exclude` file in the checkout's git directory, named by `core.excludesFile` in its `config.worktree` (this sets `extensions.worktreeConfig` on the repository, and the file replaces the user's global excludes file for that checkout). FakeRepo keeps the list per checkout, under `.gitignore` and `info/exclude`.
- `Worktree.park(base, *, keep_ignored=False)`: with `keep_ignored`, the ignored untracked files of now (a wholly ignored folder is one entry) are added to the checkout's own excludes as exact-path rules before the checkout, so they stay ignored and on disk at `base` whatever its `.gitignore` says. When `base` tracks a file among them (the checkout would overwrite it) it raises the new `IgnoredFilesWouldBeOverwritten(paths)` and nothing changes.
- `ignore_rules.literal_pattern(path)`: the rule that matches exactly one path (glob characters, leading `!`/`#` and trailing spaces escaped). FakeGit's matcher now reads `\x` as one literal character.

## 0.19.0

Three operations a caller needs to preserve a checkout's work as a commit on a branch without touching that checkout, with real and fake under one contract:

- `Worktree.capture() -> TreeId`: the tree of the checkout's final working state, made through a private copy of the index (`GIT_INDEX_FILE`), so the real index, HEAD, refs and working files are untouched. It starts from the paths already indexed (an indexed path stays in even when an ignore rule now matches it), `add -A` lets every working file win over its staged version and records deletions, and untracked files that no ignore rule hides come in; ignored untracked files stay out and on disk. Unresolved merge entries raise the new `UnmergedPaths(paths)`, and a repository nested in the checkout (a gitlink git would record instead of its files) the new `EmbeddedRepositories(paths)`; nothing is half-made. Filters configured for the repository still run, as for `record`.
- `Repo.commit_tree(tree, parents, message, *, when=None) -> Sha`: a commit of a tree id with exactly the given parents, in order (none: a root commit), in Git objects only (`git commit-tree --no-gpg-sign`: no ref, index, checkout or hook), with the repository's identity. With `when` (seconds since the epoch, UTC) both dates are fixed, so the same tree, parents, message and `when` give the same commit id and a caller that crashed before recording it gets it back. A missing tree or parent raises `MissingRevision`.
- `Repo.update_ref(ref, new, *, expected) -> RefUpdated(sha) | RefMoved(actual)`: compare and swap in one `git update-ref` call; `expected=None` means the ref must not exist, and `RefMoved.actual` is what the ref names now (None: nothing). Nothing changes on `RefMoved`. A checkout that has the branch out keeps its old index until `Worktree.reset(new)` (mixed) brings it up, with no working file touched.

## 0.18.1

- A bounded read (`read_timeout`) runs as the leader of its own process group (`real_spawn.run`) and its timeout kills the whole group, so a Git child (the fsmonitor program, a filter, a per-submodule `git`) blocked on the same file no longer outlives the timeout holding the pipes. Writes and remote calls keep `subprocess.run`. The residual changes: a process in another group or session, or one stuck in an uninterruptible file-system call (a dead NFS mount), still waits.

## 0.18.0

- `RealRepo(read_timeout=seconds)`: every read-only command (`status`, `diff`, `ls-files`, `ls-tree`, `rev-parse`, `rev-list`, `merge-base`, `cat-file`, `log`, `cherry`, `grep`, `for-each-ref`, `check-ignore`, `worktree list`; `real_reads.is_read`) is killed after that many seconds and raises `GitTimeout` ("git status timed out after 2s"), so a read that blocks (a FIFO at `$GIT_DIR/info/exclude`) no longer hangs the caller. Those commands also run with `GIT_OPTIONAL_LOCKS=0`. Writes (commit, checkout, add, update-ref, ...) are never bounded: killed midway they leave `index.lock`. Default `None`: no bound, nothing changes. A command Git cannot be killed out of (a dead NFS mount) still waits.

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
