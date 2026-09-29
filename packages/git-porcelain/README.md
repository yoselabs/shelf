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
                       author=git.Identity("Robin Vale", "robin@example.com"), committer=me,
                       trailers=[("App-Entity", "note/a")])     # None when nothing changed
for c in git.log_grep(repo, "^App-Entity: note/a$"):            # newest first, with paths
    old = git.show_at(repo, c.paths[0], c.sha)                   # None if absent there
try:
    git.push(repo)                                               # never forces
except git.RemoteError as e:
    e.reason                                                     # offline | auth | rejected | other
```

- `commit_paths` commits exactly the paths given — additions, edits, deletions, renames —
  and leaves anything else the user staged alone. Identity is per call (a box with no
  `user.name` still commits); hooks are skipped; a held `index.lock` raises and is never
  removed.
- `status` returns one `StatusEntry` per file with `tracked` and a rename's `orig_path`;
  paths are unquoted (non-ASCII names come back as written, not as git's octal escapes).
- `fetch` + `is_ancestor(repo, "origin/main", "HEAD")` tells whether a push would
  fast-forward. Nothing here pulls or merges into a working tree.

## Surface

`run_git`, `git_returncode`, `is_repo`, `has_upstream`, `upstream`, `head`,
`merge_in_progress`, `sync_status`, `readiness`, `status`, `dirty_rels`, `unmerged_paths`,
`has_conflict_markers`, `show_stage`, `show_at`, `commit_paths`, `log_grep`, `push`,
`fetch`, `is_ancestor`, `classify_remote_failure`, and the types `Identity`, `Commit`,
`StatusEntry`, `GitError`, `RemoteError`. Interpreting the git data (mapping conflicts to
your domain, etc.) is the caller's job.
