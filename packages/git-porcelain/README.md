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

- **`Repo`**: `identity sync fetch remote_url ls_remote delete_remote_at is_ancestor merge_base cherry relate history count refs tag branches rename_branch delete_branch tree squash worktrees add_worktree drop_worktree
  prune_worktrees worktree_state exclude_locally worktree`.
- **`Worktree`**: `health branch checkout checkout_new clean reset checkout_force snapshot diff dirty stage stage_tracked record merge_ff take_branch release_branch park rebase_onto
  finish_rebase rebase continue_rebase abort_rebase rebasing unmerged push push_refspecs push_request push_lease lfs_push landed grep_tracked`.
- **Results are frozen unions** (`Recorded | NothingToRecord | HookRejected`, `BranchTaken |
  BranchHeld`, `UpToDate | Rebased | Conflict`, `Squashed | Conflicted`, `Pushed | Rejected | Transient`, `Synced | Offline`,
  ...), shared records live in `git_porcelain.api`. An expected condition is a variant, except
  worktree removal's `WorktreeRemoveRefused` diagnostic. An
  infrastructure failure raises `GitUnavailable` (`.tail`, `.retryable`, `.hint`). A caller
  precondition raises `ValueError`.
- **Checkout primitives**: `branch()` returns symbolic HEAD's short name, even for an unborn
  branch, or `None` when detached. `checkout(ref)` switches to an existing local branch or
  detaches at a commit-ish; it never creates a tracking branch implicitly. `checkout_new(branch,
  start="HEAD")` creates exclusively, raising `BranchExists` for an existing branch.
  Compatible local edits survive ordinary checkout; edits that would be overwritten raise
  `DirtyTree`. A branch held by another worktree raises `BranchPinned` with its `holder`.
  `checkout_force(branch, start)` runs checkout with `-B -f`: create or reset the branch and
  discard local changes, while still respecting another worktree's branch pin.
- **Cleanup and reset**: `clean(keep=(), ignored=False, nested=False)` removes untracked files and directories
  except gitignore-style `keep` patterns, without moving HEAD or changing tracked files.
  `ignored=True` also removes ignored files. `nested=True` also removes nested repositories (git skips a
  directory holding its own `.git` without a second `-f`); `ignored=True, nested=True` is `git clean -ffdx`.
  `dirty(ignored_under=["."])` then lists what is still ignored in the whole checkout (empty after that clean). `reset(rev, mode="mixed")` moves HEAD; `soft`
  preserves the index and working files, `mixed` resets the index, and `hard` also resets tracked
  files, discarding edits. Unrelated untracked files survive a hard reset or forced checkout;
  untracked files obstructing the target's tracked files may be removed by git.
- **Branch maintenance**: `rename_branch(old, new)` renames without replacing an existing
  destination (`BranchExists`). `delete_branch(branch, expected=sha)` uses atomic
  compare-and-delete (`update-ref -d`); a moved or missing tip raises non-retryable `RefRace`.
  A branch checked out in any worktree raises `BranchPinned`, preserving its tip and HEAD.
  There is no merged check. No retry can delete a newly advanced tip.
- **Recording scopes**: `record(message, paths="own", base=None, mode="new", squash_to=None,
  hooks=False, allow_empty=False)` keeps the original `own` and `all` behavior. `tracked` stages
  modifications/deletions of index-tracked paths and commits them with already staged additions;
  untracked files stay out. `staged` commits the existing index contents, preserving staged blob
  contents and leaving unstaged edits and untracked files alone. `mode="amend"` replaces HEAD
  rather than adding a child, including message-only amendments; an empty message keeps HEAD's
  message. An unborn HEAD cannot be amended. `squash_to` retains its existing soft-reset behavior.
  Hooks run only with `hooks=True`; their refusal returns `HookRejected`. An unchanged index
  returns `NothingToRecord` for a new commit unless `allow_empty=True`.
  `Recorded.output` contains complete stripped stdout plus stderr, including successful hook output.
  `HookRejected.output` retains the entire diagnostic; `tail` is a short display excerpt, even when the hook
  prints no hook name. Commit rejection requires positive hook evidence: a hook name, a hook failure
  marker, or the hook's own output with hooks enabled. Git failures, including unresolved
  conflicts, unborn amendments, signing, identity and lock failures, raise `GitUnavailable`
  (or its typed subclass).
  Failures with hooks disabled also raise. Those exceptions carry complete combined command output
  in `output`. `NothingToRecord.output` defaults to empty because no commit command ran.
  Conflict-marker text is not a precondition; git decides whether the selected index can commit.
- **`RealRepo` owns the environment**: it strips the variables that make `-C` lie, forbids prompts,
  pins `GIT_DIR`/`GIT_WORK_TREE` from the checkout's `.git` (re-read on every call), sets `LC_ALL=C`, and runs hooks:
  `record(hooks=False)` skips them, `push` always runs `pre-push`. Under `user.useConfigOnly` a
  missing identity is a `GitUnavailable` whose hint says to set `user.name` and `user.email`.
- **A verified git directory**: `RealRepo(path, pins={path: git_dir})` pins each listed checkout to the git
  directory the caller already checked, on every call, and never reads `<checkout>/.git` again: a process that swaps
  or deletes the pointer after the check cannot aim a commit (or a `clean` filter, a hook) at another git directory.
  Keys are the exact paths the repo and its worktree views are opened with; a call anywhere else raises `NotARepo`
  before any git process runs, so git never discovers an enclosing repository. `health` runs pinned too.
- **`RealRepo` memoizes inside**: identity and shas are kept for good; `worktrees` until the
  repo's own write or `invalidate()`; ref-named answers are checked against file signatures of
  HEAD, loose refs, `packed-refs` and `shallow` (a reftable repo skips the memo); `health`,
  `snapshot` and `dirty` are never served blind. `snapshot` skips the index work when the status
  text and each listed file's (size, mtime_ns, mode, inode, sha1) are unchanged, so a same-size
  edit in the same clock tick is still seen. A change made by another process to something the
  signatures do not cover needs `invalidate()`.
- **Explicit landing operations** supplement `push(dst)`; their contracts are described below.
- **Worktree pools** stay pinned to the checkout's `.git`, including add, remove and prune.
  `add_worktree(path, rev, force=True)` passes `--force`: it recreates a registered checkout
  whose folder disappeared, still detached at `rev`; it cannot replace a live checkout.
  `prune_worktrees()` independently prunes stale registrations and invalidates the worktree memo.
  `drop_worktree(path, force=False, missing_ok=True)` retains the original absent-folder acceptance
  and prune behavior. With `missing_ok=False`, it requires a registered linked worktree and removes
  only that registration, even if its folder is gone; it never prunes other registrations.
  Removal refusals raise `WorktreeRemoveRefused` (a `GitUnavailable` subclass) with `.reason` equal
  to the final nonempty stderr line, so a caller can explain why the checkout stayed. Dirty checkouts
  need `force=True`; infrastructure errors retain their own types.
  `worktrees()` reads NUL-delimited porcelain: quotes, tabs, newlines and non-ASCII path bytes
  round trip, and incomplete records raise `GitUnavailable`.
- **`repo.worktree_state(path)`** returns the exact bytes from
  `git --no-optional-locks status --porcelain=v2 --branch -z --untracked-files=all`.
  It is never memoized, preserves raw path bytes and branch headers, omits ignored files,
  and returns `None` when the path is not a worktree. Other read failures raise.
  These are task-loop's `treehash.state_of` status bytes; callers still need file stats/content
  to distinguish successive edits with the same status. This read leaves the index untouched.
- **`FakeRepo`** (`git_porcelain.testing`) models the domain state (refs, objects hashed as git
  hashes them, index, files, config, worktrees, remotes, a paused rebase). Arrange with
  `FakeRepo.init/clone`, `add_remote`, `set_remote_url`, `set_config`, `hooks`, `drop_checkout`,
  `FakeRemote.advance/offline`, and on the worktree `write_file`, `read_file`, `remove_file`,
  `write_markers`, `redirect_toplevel`, `lock_index`. Paths are virtual.
- **Fidelity gaps of the fake** (documented, not hidden): no signing, no rename detection in a
  diff (`Change.kind` is never `R`), a `.gitignore` below the root is not read, only rebases merge,
  the commit's author is not kept, and the `real_only` scenarios (ref-lock races, a broken
  `core.worktree`, git missing) run on real git only.
  Its `worktree_state` emits deterministic porcelain v2 bytes from virtual HEAD/index/files,
  with regular-file modes, exact-content staged renames, and placeholder stages for unmerged paths.
  It has no filesystem stats, executable/symlink/submodule modes, upstream status headers, or
  similarity-based rename detection; its synthetic commit ids differ from real git's. Refusal
  reasons model absent, main and dirty worktrees; filesystem permissions, locked worktree
  registrations and submodule removal refusals are not modeled. Pruning is immediate for missing
  virtual checkouts; git can retain registrations according to lock and expiration rules.
  The fake assumes descendant directories exist; it cannot distinguish an absent subdirectory
  inside a live checkout from an existing one when answering `worktree_state`.
  Checkout/reset/clean operate on virtual regular files: no nested-repository protection,
  filesystem permission failures, file/directory obstructions, reflogs or branch config migration.
  Ordinary checkout conservatively refuses changed paths with local edits rather than modeling
  every index merge exception git accepts. Branch-name validation, previous-checkout shorthand,
  and tracking configuration are not modeled. Clean uses the fake's root-only ignore matcher.
  Hooks remain refusal knobs; staged contents and amend parents/messages are modeled, while
  author/committer metadata and commit ids differ from real git. Index locks are simulated by
  `lock_index`; actual ref-lock contention runs only on real git.
- **It cannot drift:** `tests/features/git_contract.feature` (`@contract`) holds one scenario per
  behaviour and runs against `RealRepo` on temp repos and against `FakeRepo`. Add a scenario before
  teaching the fake a new behaviour. `tests/test_real_git_cache.py` covers the memo rules on real git.

## Surface

### Small repository and index operations

`Worktree.stage(paths, literal=True)` stages additions, edits and deletions for the supplied
paths using `git --literal-pathspecs add -A --pathspec-from-file=- --pathspec-file-nul`.
Names containing whitespace, newlines, leading dashes and wildcard characters are literal by
default; all paths travel through stdin, without an argv size limit. Empty paths stage nothing.
`literal=False` enables git pathspec matching. `stage_tracked()` uses `add -u` and includes
already staged additions, leaving untracked files alone. Both are stage-only operations;
neither commits. Missing/ignored paths and index failures raise `GitUnavailable` or its typed
subclass (`IndexLocked` for a held index lock).

`Repo.tag(name, rev)` creates a lightweight tag without signing or replacing an existing tag.
An existing tag raises `TagExists`; an absent revision raises `MissingRevision`. Other git
failures raise `GitUnavailable`. `Worktree.merge_ff(rev)` runs `merge -q --ff-only`, with the
same environment and checkout pinning as other writes. Divergence raises `NotFastForward`,
an absent revision raises `MissingRevision`, and local edits that would be overwritten raise
`DirtyTree`; other failures raise `GitUnavailable`. All these errors extend `GitUnavailable`.

`Repo.count(include, exclude=())` counts commits reachable from the included revisions minus
those reachable from excluded revisions (`rev-list --count` with `^revision` exclusions).
Overlapping includes count each commit once. An empty include returns zero, without an
implicit HEAD or revision lookup. Missing include/exclude revisions raise `MissingRevision`;
other git failures raise `GitUnavailable`.

`Repo.refs(prefixes)` returns sorted `RefEntry(name, sha)` tuples from
`for-each-ref --format="%(objectname) %(refname)"`. Names retain their full namespace.
Arbitrary ref prefixes and git patterns are accepted. Passing `[]` intentionally lists every
ref under `refs/`, across all namespaces.
No matches return an empty tuple; command failures raise `GitUnavailable`.
`Repo.ls_remote(remote, patterns=())` returns `RemoteRef(name, oid)` tuples, including HEAD
and peeled tags, filtered by git's tail globs. No matches return an empty tuple; transport
and command failures raise `GitUnavailable`. It uses `RealRepo`'s injected environment and
remote timeout, unlike the path-only `git_porcelain.ls_remote` function. Leading-dash remotes
raise `ValueError`. The fake advertises registered remotes, with its existing annotated-tag
and transport limitations.

### Rebase and landing operations

`Worktree.rebase_onto(base, squash_message=None, squash_failure="raise", update_refs=None)`
inherits `rebase.updateRefs` when `update_refs` is `None`; `True` enables it and `False`
overrides configuration. Failed squash commits restore the original HEAD and work before
raising. `squash_failure="continue_unsquashed"` instead replays the original commits and
returns the complete squash diagnostic in `Rebased.squash_failure` or
`Conflict.squash_failure`. Conflicts remain paused; `abort_rebase(restore_to=original)`
can restore the pre-squash HEAD.

`rebase(base, update_refs=None)`, `continue_rebase(stage_conflicts=False,
check_markers=False, missing_ok=False)` and `abort_rebase(missing_ok=True, restore_to=None)`
return `CommandResult(ok, output)`. These preserve complete stripped stdout plus stderr;
git refusals are `ok=False`, while invocation failures raise. `rebase` first resolves `base`
to a commit OID with `rev-parse --verify --end-of-options`; an absent base raises
`MissingRevision`. It then runs `git rebase -q <oid>`, including for dirty trees and already
paused rebases, adding `-c rebase.updateRefs=true|false` only for an explicit `update_refs`
value. It still runs when `HEAD..base` is empty.
Revision inputs beginning with `-` raise `ValueError("revision must not start with '-'")`
in both implementations before git can interpret them as options.
Continuation uses the caller's index by default; staging conflicted paths and checking markers
are explicit choices.
`rebasing()` checks both backends in the checkout's actual git directory; `unmerged()`
freshly reads NUL-delimited paths in git order, including merge conflicts. Observation
faults raise `GitReadFailure`, rather than manufacturing an empty answer.

`Repo.is_ancestor(a, b)` uses one `git merge-base --is-ancestor --end-of-options a b` process: equality and
ancestry return `True`, other histories return `False`, and missing revisions raise
`MissingRevision`. Other observation failures raise `GitReadFailure`.
`Repo.merge_base(a, b)` returns a SHA or `None` for verified missing revisions or unrelated
histories. It uses one `git merge-base --end-of-options a b` process on success or unrelated histories;
revision verification runs only after a failure. Other observation failures raise
`GitReadFailure`. `branch()` uses one `git symbolic-ref --short -q HEAD` process, including
for detached and unborn HEAD. `Repo.cherry(upstream, head)`
returns oldest-first `Pick(oid, upstream)` rows matching git cherry's non-merge selection;
`upstream=True` denotes patch equivalence. `Repo.remote_url(remote)` uses remote get-url,
including URL rewrites; missing named remotes raise `MissingRemote`, distinct from failed
observations. Both errors extend `GitUnavailable`. `remote_url(remote, push=True)` is
`remote get-url --push`: the first explicit `pushurl` (with `insteadOf` applied, `pushInsteadOf`
ignored), else the URL rewritten by `pushInsteadOf`, else by `insteadOf`. A caller that reads a
remote to decide what a push delivered compares the two to know both go to one repository.

`Repo.squash(onto, head, message)` makes one commit whose parent is `onto` and whose tree is
`head`'s changes merged onto `onto` over their merge base, in Git objects only: `git merge-tree
--write-tree` then `git commit-tree --no-gpg-sign -p <onto>`. No checkout, index, HEAD or ref
changes, no hook runs and nothing is signed; author and committer are `RealRepo(identity=...)`, else
git's configuration. It returns `Squashed(sha, tree)` (no ref names the commit until a push or ref
write does) or `Conflicted(paths)`, each conflicted path once, with nothing made. When `onto` is an
ancestor of `head` the tree is `head`'s; when `head`'s changes are already on `onto` it is `onto`'s.
Missing revisions raise `MissingRevision`, unrelated histories `GitUnavailable`. Git 2.38 or later.

`Repo.fetch(remote="origin", refspecs=(), timeout=None)` accepts a named remote or a source
URL/path, writes `FETCH_HEAD`, and returns `CommandResult(ok=True, output=...)`.
It and `sync` retry only ref-race failures, with at most five attempts and one process per
attempt. Other failures return immediately. Exhaustion raises the final error from `fetch`
and returns `Offline` from `sync`. `fetch(source, refspecs=[ref])` is the scoped fetch operation;
there is no redundant `fetch_ref` method. Missing remote refs raise. `timeout=None` means
no timeout. `Repo.delete_remote_at(remote, ref, expected)` sends an explicit expected-SHA
lease with a deletion refspec. `ref` must start with `refs/`; short names raise `ValueError`
before invoking git. Success returns `CommandResult`. The default `missing_ok=True`
preserves idempotency: after refusal, one advertisement verifies absence. A failed probe
raises `GitReadFailure`, carrying its complete `output` and the original `push_output`.
Pass `missing_ok=False` for exactly one process: every refusal then raises the original
push error with complete output, including a stale lease on an already absent destination.

`Worktree.push_refspecs(remote, refspecs, *, force=False, allow_delete=False, hook_env=None, timeout=None)` supports explicit
OIDs, full namespaces, multiple updates and deletion. It returns `Pushed`, `RefRejected`
(a `Rejected` subclass for non-fast-forward/stale races), `HookRejected`, `RemoteRejected`
(policy/other per-ref refusal), or `Transient`. Diagnostics are complete combined output.
For multiple updates, `Pushed.sha` identifies the first supplied source; a deletion-only
request returns `Pushed(Sha(""))`: the empty sha means nothing was pushed, only deleted.
`push(dst)` uses the same classification. `RefRejected` requires every porcelain ref row
to be `! [rejected]` with non-fast-forward, fetch first or stale info; remote policy
refusals remain `RemoteRejected` even when hook text contains "rejected".
`HookRejected` requires no ref status rows and Git's trace evidence that pre-push exited
with a nonzero status. A hook that passed before a connection drop remains `Transient`.
Silent hooks and hooks printing only `error:` are supported, including configured hook paths.

`push_request(remote, refspecs, *, options=(), force=False, allow_delete=False, hook_env=None, timeout=None)` returns
`CommandResult` for configured landing forms, including omitted remote/refspec defaults,
`HEAD`, `HEAD:main`, `+HEAD:main`, OIDs, tags, deletion and multiple refs. Exact HEAD
sources are resolved by the push process itself; force prefixes and explicit destinations survive.
A bare HEAD retains Git's symbolic branch destination. For an explicit refspec with omitted
remote, selection follows branch pushRemote, remote.pushDefault, branch remote, then origin.
Normal pre-push hooks, checkout pinning and the repository's injected environment remain
in force. Both push methods reject leading `+` without `force=True`, and empty-source
deletion refspecs (`:destination`) without `allow_delete=True`, before invoking git.
In `push_request`, `--force`/`-f` require `force=True`; `--delete`/`-d` and `--prune`
require `allow_delete=True`; `--mirror` requires both. `--force-with-lease[=...]`
remains allowed. Opt ins authorize the supplied forms; they do not add push options.
Remote arguments starting with `-` raise `ValueError` in push, fetch, sync and guarded
remote deletion. Other options pass to git without changing configuration or upstream settings.
`push_lease(remote, refspec, timeout=3600)` uses plain `--force-with-lease`, preserving
stale-info refusals. `lfs_push(remote, refs, timeout=3600)` invokes LFS once with all refs,
without setup or hook installation. Its default timeout outcome is
`CommandResult(False, "git lfs timed out after 60 min")`. Command-style push timeouts also
return failure outcomes; spawn failures raise.

### Behavior notes 0.12

Version **0.12.0** retains complete, stripped stdout followed by stderr in `output` on every
remote result and failure. `tail` is only a short display diagnostic. `Repo.ls_remote`
returns `RemoteRefs`, a tuple with `output`; the path-based function returns `Refs`, a list
with `output`. Path-based push, fetch, LFS push/fetch and pull/rebase now return
`CommandResult` instead of `None`; their exceptions retain full `output`, too. Timeouts
retain whatever output Git produced before the deadline.
`readiness` includes the remote probe's complete diagnostics in its `output` dictionary entry.
Typed rebase results also expose `output`; merge results retain complete `output` and
untruncated blocked-merge `error`. `HookRejected.tail`, including commit-hook refusals,
and exception `tail` values are display excerpts of at most 600 characters.

Diagnostic `output`, `tail` and exception text redact URL userinfo:
`https://user:pass@host/repo` becomes `https://***@host/repo`, and
`http://user@host/repo` / `ssh://user@host/repo` hide the username too. This covers both
output streams and partial timeout output. Invalid UTF-8 bytes become replacement
characters in diagnostic text. Raw byte reads and parsed values such as configured remote
URLs retain their data. This is URL userinfo redaction, not a general secret scanner.

`push(dst)` sends `<sha>:refs/heads/dst`, pinning HEAD before the push. The pre-push hook's
stdin local-ref field is therefore that full SHA, rather than `HEAD`; its local-object-id
field is the same SHA. `push_request` still lets Git resolve its supplied HEAD refspec.

Hook classification requires Git **2.37+ (verify)** for the `hook_name` field in trace2
`child_start`, matched to the same child's `child_exit` status. Without that evidence, an
otherwise unclassified refusal raises `GitUnavailable` with complete redacted output;
hook wording alone never produces `HookRejected`. Recognized transport failures remain
`Transient` even without trace evidence.

Process budgets (top-level git invocations, excluding processes Git itself launches):

| Operation | Processes |
|---|---|
| `push(dst, head=known_sha)` | 1 |
| `push(dst)` | 2: resolve a full SHA, then push that pinned object |
| `push_refspecs` with full OIDs or deletions | 1 |
| `push_refspecs` with a symbolic source | 2; bare `HEAD` needs a third to preserve its branch destination |
| `push_request` with a remote, `push_lease`, `lfs_push` | 1 |
| `push_request(None, explicit_refspecs)` | 3: symbolic branch, one config query, push |
| `push_request(None, [])` | 1 |
| `fetch`, `sync` | 1 per attempt; at most 5, retrying only ref races |
| `ls_remote` | 1 |
| `delete_remote_at(..., missing_ok=False)` | 1 |
| `delete_remote_at` with default idempotency | 1 on success, 2 after refusal to distinguish absence from a moved ref |
| Path-based push, fetch, LFS push/fetch, pull/rebase, ls-remote | 1 |
| `readiness` with a remote probe | 3: identity, configured remotes, ls-remote |

Push porcelain omits full object IDs on new and up-to-date refs. Typed pushes therefore
need resolution unless the caller supplies the object ID: use `push(dst, head=known_sha)`
or a full-OID refspec to keep the one-process budget. Command-style pushes have no SHA to
return. Hook detection reads Git trace events from the same invocation and adds no process.
Push calls reserve `GIT_TRACE2_EVENT` for that temporary capture.

The fake models branch rewrites (excluding branches held by worktrees), leases against
fetched tracking refs, explicit push refspecs, guarded deletion, FETCH_HEAD, named URL
rewrites and staged continuation. Mirror and wildcard pruning model remote ref deletion.
`FakeRepo.hooks.commit_failure` injects a non-hook commit failure; no signing runs in memory.
`hooks.commit_output` supplies complete hook output, and `hooks.rebase_result` and
`hooks.rebase_spawn_failure` model a command refusal or invocation failure even on an up-to-date base.
`hooks.push_output` supplies the complete output of a refusing pre-push hook, including an
empty string for a silent refusal. The fake applies successful refs in a partial push and
classifies the combined outcome using all ref rows.
`hooks.push_transport_failure` models a transport failure after a passing hook;
`hooks.fetch_ref_races` injects ref races consumed within the same five-attempt fetch budget.
Its diagnostics are representative, while real git owns
exact success and refusal wording. Scoped fetch sources must identify a registered
`FakeRemote`; arbitrary transports, wildcard fetch refspecs, shallow histories, annotated
tags, complex cherry patch/context equivalence and Git's ordering tie-breaks for complex
graphs remain outside the fake. URL rewrite config keeps the fake's normalized-key limitation.
The fake supports force, lease, dry-run and delete push options and basic clone upstream
defaults; arbitrary configured push modes/options (including atomic transactions and server
push options) are deliberately refused rather than simulated as successful. Real git accepts
those options. Full emulation is entangled with Git's configuration and transport protocols.
LFS transfer/storage is not simulated: `hooks.lfs_available` and `hooks.lfs_push_failure`
control outcomes; `hooks.lfs_spawn_failure` raises an invocation error. LFS is unavailable
by default. The real operation uses installed git-lfs. Successful transfer and deadline
contract scenarios inject the process result in the real lane; the unavailable/failing
command scenario invokes the real binary.
Fake timeouts, filesystem failures, real hook execution and rebase backend differences are
not simulated. Contract scenarios exercise the shared public methods against both lanes;
the squash-failure scenario injects a process refusal in the real lane.

The path-based plumbing also exports `Ref(name, oid)`, `ls_remote(repo, remote, *patterns)`,
`branches(repo, remote=None)` (short names, local or that remote's tracking branches),
`delete_ref_at(repo, ref, oid)` (atomic compare-and-delete), `config_get(repo, key, default=None)`,
`config_entries(repo, pattern)`, `symbolic_ref(repo, name)`, `merge_ff(repo, ref)`,
`pull_rebase(repo, remote, branch)`, `check_ignore(repo, paths)` (`--no-index`), and
`ls_files(repo, scope="tracked" | "untracked" | "ignored" | "all")` (sorted paths).
Git diagnostics raise `MissingRevision`, `NotARepo`, `IndexLocked`, `RefRace`, `DirtyTree`, `BranchExists`, or `BranchPinned`
(`holder` is the other worktree); all extend `GitUnavailable` and `GitError`.
`FakeRepo.plumbing()` supplies the same path-taking calls (`FakePlumbing` in `testing`).
It inherits the fake's ignore/merge limitations; config has one value per normalized key and Python
regex matching rather than git's POSIX regex dialect, no global/include config, no annotated tag
peeling, no filesystem ref-lock races, no arbitrary remote transport, and no hook execution.
Pull uses the modeled named remote, without custom refspecs or config-driven autostash.
`Worktree.snapshot(base, inputs=[...])` force-includes literal input files/directories even when
ignored, without changing the real index; declared inputs bypass the snapshot cache.
A declared directory includes all its files recursively, including ignored descendants; ignored
files outside it remain excluded. An input matching no files raises `GitUnavailable` in both the
real and fake implementations.
Task-loop's `treehash.state_of` is a status/stat signature, while `tree_of` is the matching tree-id
operation: both omit ignored files by default. Explicit `inputs` extends that default for declared
ignored inputs; ordinary snapshots retain `tree_of` semantics.

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
