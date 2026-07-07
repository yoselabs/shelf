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

## Surface

`run_git`, `is_repo`, `has_upstream`, `merge_in_progress`, `sync_status`, `readiness`,
`unmerged_paths`, `has_conflict_markers`, `show_stage`, `dirty_rels`, and `GitError`.
Interpreting the git data (mapping conflicts to your domain, etc.) is the caller's job.
