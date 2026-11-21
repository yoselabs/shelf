# Changelog

## 0.30.0

- New `Worktree.clean_nested(keep=())` (`git clean -ffdx`): `clean_ignored` that also deletes nested repositories, the mode `clean(nested=True)` had before 0.27. Destructive: a nested repository goes with its history and uncommitted work. `FakeRepo` holds no nested repositories, so there it equals `clean_ignored`.

## 0.29.0

- The real runner uses stream-proc 0.13.0's one `capture` (`Captured`; `err_text` for the display copy); requires `stream-proc>=0.13.0,<1`. Contract unchanged.

## 0.28.0

**Breaking**: the `Literal` policy parameters are gone (Article III; ADR 0030). Each mode is its own verb, or deleted where the caller can compose it.

- `Worktree.finish_rebase(action, *, restore_to=None)` deleted, with `FinishResult` and `Aborted`: use `resolve_and_continue()` and `abort_rebase(*, restore_to=None)`, which return `CommandResult`.
- `Worktree.rebase_onto(..., squash_failure=)` => `rebase_onto(base, *, squash_message=None, update_refs=None)`: a failed squash always restores the original work and raises `GitUnavailable`; `Rebased.squash_failure` and `Conflict.squash_failure` are gone. To go on unsquashed, call `rebase_onto(base)` again.
- `Worktree.record(..., mode=, squash_to=)` and `record_with_hooks(..., mode=, squash_to=)` => `record(message, *, paths, base)` (new commits only), `record_with_hooks(...)` and new `amend(message="")` (HEAD replaced by the index as it is; no hooks, no staging: stage first). `mode="squash_to"` is `reset(fork, mode="soft")` then `record(message, paths="staged")`.
- `Worktree.take_branch(branch, base, *, mode=, keep_aside_as=, clean_keep=)` => `take_branch(branch, base, *, clean_keep=None)` (`resume`) and new `restart_branch(branch, base, *, keep_aside_as=None, clean_keep=None)` (`fresh` and `restart`: `keep_aside_as=None` is the old `restart`).

## 0.27.0

**Breaking** (shelf-tyld.26): tolerance and destructive flags are gone (Article III: tolerance is a handler, not a flag; ADR 0030). Store bytes unchanged.

- `Repo.delete_remote_at(remote, ref, expected, *, missing_ok=True)` => `delete_remote_at(remote, ref, expected)`: one process; a refusal (moved or already-absent ref) raises `GitUnavailable` with git's output. The old tolerant path (the extra `ls-remote`, `GitReadFailure`) is gone: catch `GitUnavailable`, ask `ls_remote`.
- `Repo.drop_worktree(path, *, force=False, missing_ok=True)` => `drop_worktree(path)` (registered linked worktree; clean) and `discard_worktree(path)` (drops changes). A path git does not know raises the new `NotAWorktree` (a `WorktreeRemoveRefused`); the old default also pruned every stale registration: call `prune_worktrees()`.
- `Repo.add_worktree(path, rev, *, force=False)` => `add_worktree(path, rev)`: a registered-but-missing checkout refuses; `drop_worktree(path)` it first.
- `Worktree.continue_rebase(*, missing_ok=False)` => `continue_rebase()` (`ok=False` with no rebase paused); `abort_rebase(*, missing_ok=True, restore_to=None)` => `abort_rebase(*, restore_to=None)` (idempotent).
- `Worktree.push_refspecs` and `push_request` lose `force=` and `allow_delete=` and now always refuse force and deletion forms (leading `+`, `:dst`, `--force`/`-f`, `--delete`/`-d`, `--mirror`, `--prune`, `--force-with-lease`) with the new `PushRefused(GitError)` (was `ValueError` unless the flag was passed). No force or delete push verb: no caller needs one (`push_lease` and `delete_remote_at` stay). A leading-`-` remote still raises `ValueError`.
- `Worktree.clean(keep, *, ignored=False, nested=False)` => `clean(keep)` and `clean_ignored(keep)` (`git clean -fdx`). `nested=True` (`-ff`, deleting nested repositories) is removed: a nested repository is left in place.
- `Worktree.record(..., hooks=False, allow_empty=False)` => `record(...)` (no hooks), `record_with_hooks(...)` and `record_empty(message)` (`git commit --allow-empty` of the index).
- `Worktree.park(base, *, clean_keep=None, keep_ignored=False)` => `park(base, *, clean_keep=None)`, which always keeps the ignored files (was the `keep_ignored=True` behaviour; `IgnoredFilesWouldBeOverwritten` when base tracks one, nothing changes). The default no longer lets base's tracked files overwrite ignored ones.
- Migrate: catch `NotAWorktree` / `GitUnavailable` where you passed `missing_ok=True`; use the new verbs where you passed `force`, `ignored`, `hooks`, `allow_empty`.

## 0.26.0

**Breaking** (shelf-tyld.6): the library no longer reads `os.environ`; the caller passes its environment at its edge.

- `RealRepo(path, *, ambient=...)`: `ambient` is required (was optional; without it each call read the live process environment). The snapshot is taken once; a later change to the process environment does not reach git.
- Every path function that runs git takes a required keyword `ambient`: `run_git`, `run_git_result`, `git_returncode`, `has_upstream`, `sync_status`, `readiness`, `unmerged_paths`, `show_stage`, `dirty_rels`, `status`, `head`, `log_grep`, `show_at`, `is_ancestor`, `upstream`, `push`, `fetch`, `merge`, `finish_merge`, `commit_paths`, the `lfs_*` functions (`lfs_available(*, ambient)` too), `ls_remote`, `branches`, `delete_ref_at`, `symbolic_ref`, `config_get`, `config_entries`, `merge_ff`, `pull_rebase`, `check_ignore`, `ls_files`. The `Plumbing` protocol methods take it too; `FakePlumbing` ignores it. `git_env(ambient)` and `real_env.base(source, extra)` take the mapping as an argument.
- `env=` keeps its meaning: variables added to one call on top of `ambient`. Child environments are built exactly as before (same stripped variables, prompt off, `LC_ALL=C`), so behaviour with `ambient=dict(os.environ)` is unchanged.
- `head()` no longer consults the process `GIT_DIR`; it checks `ambient`.
- Migrate: pass `ambient=dict(os.environ)` (read once at your `__main__`/cli) to each call above and to `RealRepo`.

Breaking (shelf-tyld.13, bool modes split into named operations; every old call maps one to one):

- `Worktree.stage(paths, *, literal=True)` ⇒ `stage(paths)` (literal) and new `stage_pathspec(patterns)` (the old `literal=False`).
- `Repo.remote_url(remote, *, push=False)` / `remote_urls(...)` ⇒ `remote_url(remote)`, `remote_urls(remote)` and new `remote_push_url(remote)`, `remote_push_urls(remote)` (the old `push=True`).
- `Worktree.continue_rebase(*, stage_conflicts=False, check_markers=False, missing_ok=False)` ⇒ `continue_rebase(*, missing_ok=False)` (existing index) and new `resolve_and_continue()` (the old `stage_conflicts=True, check_markers=True`: refuse on markers, stage every unmerged file, continue). The two flags alone, in other combinations, are gone.
- `run_git(vault, *args, check=True, ...)` ⇒ `run_git(vault, *args, ...)` (raises) and new `try_git(vault, *args, ...)` (the old `check=False`: stdout whatever the exit code).
- `RealRepo.run` / `RealWorktree.run(..., check=True, ...)` ⇒ `run(...)` (raises `GitUnavailable`) and new `try_run(...)` (returns the `Done`; the old `check=False`).
- Internal: `RealRepo.memo(forever=)` ⇒ `memo` and `memo_until_write`; the fake's `fetch(retry=)` ⇒ `fetch` and `fetch_once`.
- Stays: `missing_ok` (`abort_rebase`, `continue_rebase`, `delete_remote_at`, `drop_worktree`), `force`/`allow_delete`/`ignored`/`nested`/`allow_empty`/`hooks`/`keep_ignored`: justified exceptions, ADR 0030.
- `sync_status` returns `SyncStatus` and `readiness` returns `Readiness` (TypedDicts, exported) instead of `dict[str, Any]`; the keys and values are unchanged.

## 0.25.0

Consumer wave (shelf-tyld): git-porcelain now runs on the shelf's owners instead of its own copies. Behaviour change: **every git call is bounded**.

- Depends on `stream-proc` (the child runs through `capture_bytes`: its own session, the whole tree stopped on a timeout, partial output kept) and `child-env` (`find` locates `git` and `git-lfs` on the PATH of the env the child gets). `real_spawn.py` and its hand-written `killpg` are deleted.
- Writes used to run with no timeout; now a call that names none gets `DEFAULT_TIMEOUT` (3600 s, one constant in `git_porcelain.api`, also the `push_lease` and `lfs_push` default), and a read with `read_timeout` set keeps that bound. A timeout stops git with SIGTERM first (so it can drop `index.lock`), then SIGKILL, and raises `GitTimeout`. stdin of a call is now `/dev/null` unless `stdin=` is given.
- `git_messages.py` holds every git diagnostic the package classifies on (lock contention, pinned branch, dirty tree, missing revision, not a repo, a commit failing for a non-hook reason); `errors.py`, `real_done.py` and `real_write.py` import them. No classification changed; `tests/test_git_messages.py` pins each pattern to a real git sample.
- `real_commands.command(lfs=bool)` is `timed_out=<message>`.

## 0.24.0

A knowledge-base reader (ogy) opens a commit or the folder on disk through one interface, with no raw `git rev-parse` and no hand-made blob hash. Additive.

- `Repo.commit(rev) -> Sha`: the full id of the commit `rev` names (`rev-parse --verify <rev>^{commit}`); `MissingRevision` when it names no commit (a blob or an unknown name). FakeRepo the same, under the shared contract.
- `blob_sha(data) -> Sha`: the id Git gives a file holding `data`, so a file on disk compares with a `Tree.files` entry. Public now (it was `fake_store`'s).
- `worktree_tree(root, folder="") -> Tree | None`: the regular files on disk below `root/folder` as a `Tree` (`files`, `read`, `read_many`, `sha` as for `Repo.tree`; `sha` is the tree id Git would give those files, modes included, so equal content gives an equal id). Uncommitted and ignored files count; `.git`, symlinks and empty folders do not. `read` stays inside the folder. None when the folder is absent or a file.
## 0.23.0

Many files of a commit read as exact bytes in one git process, for a reader that loads a whole folder (a knowledge base) from the object store instead of opening each file.

- `Tree.read_many(paths) -> dict[str, bytes | None]`: each path's bytes, None when absent or not a file; the paths not read yet come in one `git cat-file --batch` (real), CRLF and invalid UTF-8 kept as they are. Shares `read`'s cache. `Tree(..., batch=)` is the optional batch reader; without it `read_many` reads one by one.
- `Repo.tree("rev:folder")`: the tree below a folder, `files` relative to it and `sha` that folder's tree id; None when the folder is absent or a file (real: one `cat-file --batch-check`). FakeRepo the same.

## 0.22.1

No behavior change. `Worktree.clean(keep=["/.venv"], ignored=True)` is the reset that keeps a named folder: a leading `/` anchors to the checkout root (a bare `.venv` keeps same-named folders below too); a symlink is removed as a link and never followed out of the checkout, a kept folder holding one is left whole. Locked by a shared contract scenario (real and FakeRepo) and real-git tests; documented on `clean`.

## 0.22.0

A diff limited to chosen paths, for "did any file I care about change between two commits" with no model call and no patch.

- `Worktree.diff(a, b, *, include=(), exclude=(), cap=None)`: `include` (literal paths, a folder standing for everything below it; empty = everything) narrows `changes` and `patch` to those paths before `exclude` leaves some out. `diff(base, "HEAD", include=cited, cap=0).changes` is the cheap changed-files read (real: `git diff --raw --numstat -- :(literal)<path>...`; FakeRepo the same). Additive.

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
