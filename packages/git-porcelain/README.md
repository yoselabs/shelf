# git-porcelain

A pure, fail-loud git surface over the **git binary** — no library, no dependencies.
Every function takes a repo path and returns git data; failures raise `GitError`,
which you translate into your own error type at the seam.

```python
import git_porcelain as git

if git.is_repo(repo):
    st = git.sync_status(repo)          # branch / clean / ahead / behind / conflict_paused
    ready = git.readiness(repo)         # repo / identity / remote / push_access
    for rel in git.unmerged_paths(repo):
        ours = git.show_stage(repo, 2, rel)   # clean stage-2 blob (marker-free)
```

## Why the binary, not a library

pygit2 and dulwich bypass the user's **credential helper + SSH agent** — you'd have to
reimplement auth the git binary gives you for free. GitPython is a maintenance-mode
subprocess wrapper that hangs on credential-helper repos. The binary is the reference
implementation the user already configured; this package just hardens it
(`GIT_TERMINAL_PROMPT=0`, `GIT_SSH_COMMAND=BatchMode`) so it fails loud instead of
hanging on a prompt.

## A program that owns a repo

```python
me = git.Identity("a2kay", "a2kay@example.invalid")
sha = git.commit_paths(repo, ["notes/a.md", "notes/old.md"], "move note/a",
                       author=git.Identity("the author", "author@example.invalid"), committer=me,
                       trailers=[("App-Entity", "note/a")])     # None when nothing changed
for c in git.log_grep(repo, "^App-Entity: note/a$"):            # newest first, with paths
    old = git.show_at(repo, c.paths[0], c.sha)                   # None if absent there
try:
    git.push(repo)                                               # never forces
except git.RemoteError as e:
    e.reason                                                     # offline | auth | rejected | other
git.fetch(repo, config={"maintenance.auto": "false"})          # no detached `git maintenance` after it
git.push(repo, config={"core.hooksPath": "/dev/null"})          # skip pre-push (git-lfs); same on lfs_push/lfs_fetch
r = git.merge(repo, "origin/main", author=me, committer=me)     # up_to_date | fast_forward |
                                                                 # merged | conflict | blocked
if r.state == "conflict":                                        # markers left, base shown
    ...                                                          # a person edits r.conflicted
    git.finish_merge(repo, r.conflicted, author=me, committer=me) # commits once markers are gone
```

- `commit_paths` commits exactly the paths given — additions, edits, deletions, renames —
  and leaves anything else the user staged alone. Identity is per call (a box with no
  `user.name` still commits); a held `index.lock` raises and is never removed. It costs
  three git processes per commit, two when nothing changed.
- `--no-verify` skips only the hooks that can refuse a commit; `post-commit` and
  `git maintenance run --auto` still run. A program committing on every write passes
  `config={"core.hooksPath": "/dev/null", "maintenance.auto": "false"}` (each entry a
  `git -c key=value`) to `commit_paths`, `merge` and `finish_merge`.
- `is_repo` and `git_dir` read the filesystem, no git process: a path inside an ancestor
  repository counts, and a `.git` file's `gitdir:` pointer (a linked worktree, a
  submodule) resolves to the per-worktree folder where `MERGE_HEAD` lives.
- `status` returns one `StatusEntry` per file with `tracked` and a rename's `orig_path`;
  paths are unquoted (non-ASCII names come back as written, not as git's octal escapes).
- `fetch` + `is_ancestor(repo, "origin/main", "HEAD")` tells whether a push would
  fast-forward.
- `merge` fast-forwards when only the other side moved and makes a merge commit (given
  identity, hooks skipped) when both did. A conflict leaves markers with the common base
  (`diff3`) and returns the paths; a local edit the merge would overwrite returns `blocked`
  and changes nothing. `changed` lists every path the merge touched, for a caller that
  re-reads them. `finish_merge` stages the conflicted paths as they now stand (edited or
  deleted) and commits once none holds a marker, so the person resolving never runs git.

## Git LFS

```python
git.lfs_setup(repo)                         # False when git-lfs is missing; config only
git.lfs_paths(repo, ["a/scan.png", "a.md"]) # {"a/scan.png"}: the paths the lfs filter owns
git.lfs_push(repo, "origin", "main"); git.push(repo)            # objects first, then the ref
git.fetch(repo); git.lfs_fetch(repo, "origin", "origin/main")   # objects before the merge
git.merge(repo, "origin/main", author=me, committer=me); git.lfs_checkout(repo)
```

- `lfs_setup` writes the filter into the repo's **local** config with
  `filter.lfs.required=true`, so a broken git-lfs fails `git add` instead of committing raw
  bytes. Attributes alone do nothing without a configured filter. It installs **no hooks**,
  so a caller uploads with `lfs_push` before every push.
- Download with `lfs_fetch` before a merge. A download failing inside the merge's checkout
  makes git restore the tree, and that restore can fail too, leaving a dirty tree and no
  `MERGE_HEAD`. `lfs_checkout` fills pointer files whose objects are already local.

## `Repo` and `Worktree` (`RealRepo`, `FakeRepo`)

A driver that makes dozens of git calls a run (task-loop's engine) takes a `Repo` and a `Worktree`.
It names an intent ("take this branch", "rebase onto base", "push to dst") and gets a typed result;
it never sees an argv, an exit code or git's English text. Whether a subprocess or a dictionary
answers is not its concern.

```python
from git_porcelain import Pushed, RealRepo, Rebased, Worktree
from git_porcelain.testing import FakeRepo

def land(wt: Worktree) -> bool:
    match wt.rebase_onto("origin/main"):
        case Rebased():
            return isinstance(wt.push("main"), Pushed)
        case _:
            return False                        # Conflict: finish_rebase("continue" | "abort")

land(RealRepo(path).worktree(path))             # the binary, memoized
land(FakeRepo.init(Path("/virtual")).worktree(Path("/virtual")))   # memory, no subprocess
```

- **`Repo`** (23 operations in all, with `Worktree`): `identity sync relate history branches tree
  worktrees add_worktree drop_worktree exclude_locally worktree`.
- **`Worktree`**: `health snapshot diff dirty record take_branch release_branch park rebase_onto
  finish_rebase push landed grep_tracked`.
- **Results are frozen unions** (`Recorded | NothingToRecord | HookRejected`, `BranchTaken |
  BranchHeld`, `UpToDate | Rebased | Conflict`, `Pushed | Rejected | Transient`, `Synced | Offline`,
  ...), shared records live in `git_porcelain.api`. An expected condition is a variant. An
  infrastructure failure raises `GitUnavailable` (`.tail`, `.retryable`, `.hint`). A caller
  precondition raises `ValueError`.
- **`RealRepo` owns the environment**: it strips the variables that make `-C` lie, forbids prompts,
  pins `GIT_DIR`/`GIT_WORK_TREE` from the checkout's `.git`, sets `LC_ALL=C`, and runs hooks:
  `record(hooks=False)` skips them, `push` always runs `pre-push`. Under `user.useConfigOnly` a
  missing identity is a `GitUnavailable` whose hint says to set `user.name` and `user.email`.
- **`RealRepo` memoizes inside**: identity and shas are kept for good; `worktrees` until the
  repo's own write or `invalidate()`; ref-named answers are checked against file signatures of
  HEAD, loose refs, `packed-refs` and `shallow` (a reftable repo skips the memo); `health`,
  `snapshot` and `dirty` are never served blind. `snapshot` skips the index work when the status
  text and each listed file's (size, mtime_ns, mode, inode, sha1) are unchanged, so a same-size
  edit in the same clock tick is still seen. A change made by another process to something the
  signatures do not cover needs `invalidate()`.
- **`push(dst)` only.** The old `cfg['land']` configurability is gone (decision 13.1): a repo that
  needs more (a different remote ref, extra checks) does it in its `pre-push` hook.
- **`FakeRepo`** (`git_porcelain.testing`) models the domain state (refs, objects hashed as git
  hashes them, index, files, config, worktrees, remotes, a paused rebase). Arrange with
  `FakeRepo.init/clone`, `add_remote`, `set_remote_url`, `set_config`, `hooks`, `drop_checkout`,
  `FakeRemote.advance/offline`, and on the worktree `write_file`, `read_file`, `remove_file`,
  `write_markers`, `redirect_toplevel`, `lock_index`. Paths are virtual.
- **Fidelity gaps of the fake** (documented, not hidden): no signing, no rename detection in a
  diff (`Change.kind` is never `R`), a `.gitignore` below the root is not read, only rebases merge,
  the commit's author is not kept, and the five `real_only` scenarios (ref-lock races, a broken
  `core.worktree`, git missing) run on real git only.
- **It cannot drift:** `tests/features/git_contract.feature` (`@contract`) holds one scenario per
  behaviour and runs against `RealRepo` on temp repos and against `FakeRepo`. Add a scenario before
  teaching the fake a new behaviour. `tests/test_real_git_cache.py` covers the memo rules on real git.

## Surface

`run_git`, `git_returncode`, `is_repo`, `git_dir`, `has_upstream`, `upstream`, `head`,
`merge_in_progress`, `sync_status`, `readiness`, `status`, `dirty_rels`, `unmerged_paths`,
`has_conflict_markers`, `show_stage`, `show_at`, `commit_paths`, `log_grep`, `push`,
`fetch`, `merge`, `finish_merge`, `is_ancestor`, `classify_remote_failure`, `lfs_available`,
`lfs_setup`, `lfs_checkout`, `lfs_paths`, `lfs_push`, `lfs_fetch`, and the types
`Identity`, `Commit`, `MergeResult`, `StatusEntry`, `GitError`, `RemoteError`, and the
`Repo`/`Worktree` protocols with `RealRepo` (above). Interpreting the git data (mapping conflicts to
your domain, etc.) is the caller's job.

## Testing helpers

```python
from git_porcelain import Identity
from git_porcelain.testing import apply_hermetic_env, git

apply_hermetic_env(monkeypatch, identity=Identity("the author", "author@example.invalid"), home=tmp_path)
git(repo, "init", "-q", "-b", "main")   # stdout; a failure raises with git's stderr
```

- `hermetic_env` / `apply_hermetic_env` shut the machine's git out: no system or global
  config, `GIT_DIR` and the other variables that point elsewhere removed, settings passed
  through `GIT_CONFIG_*` (command-line scope, so a repository's own config cannot undo them).
- `QUIET` (no hooks, no auto-maintenance, no signing, no template) is the default; a test of a
  hook or of maintenance passes `config={}`. The identity is a parameter; `None` leaves git
  with no `user.*`. Neither imports pytest.
- `FakeRepo`, `FakeWorktree` and `FakeRemote` live here too (see above).
- This package's own tests use these helpers.
