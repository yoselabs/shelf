## Why

Task-loop's pending repository inspection slice (`tl-sqd3.18.1`) needs local repository identity without reproducing Git discovery. Existing `Repo.identity()` treats failed origin observations as absent while canonical common-directory behavior needs direct contract evidence. The affected gate also reproduces a discovery classifier gap: Git's filesystem-boundary absence diagnostic becomes `GitUnavailable` instead of `NotARepo`. Both errors belong to `shelf-7qsd`.

## What changes

Verify the existing canonical common directory supplied by Git before deriving root and key. Reuse the existing typed remote read, accepting only `MissingRemote` as an absent origin. Preserve the public result shape and semantic fake. Recognize the existing filesystem-boundary discovery diagnostic in the owning classifier, preserving unknown faults as unavailable. Verify linked and symlinked paths, separate clones, and origin independence at the owning package boundary.

## Scope

No factory code, new filesystem abstraction, package version bump, tag, push or release. Task-loop adoption remains pending a published portable immutable source pin; no active use-case claim is added before adoption.
