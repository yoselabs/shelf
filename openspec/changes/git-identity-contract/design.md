## Existing ownership

`git-porcelain` owns Git discovery and process failures. `real_read.identity` owns identity derivation; `Repo.remote_url` already distinguishes `MissingRemote` from `GitReadFailure`. Catch only the former. Git guarantees `--path-format=absolute --git-common-dir` returns an absolute canonical path ([Git manual](https://git-scm.com/docs/git-rev-parse)). Both real topology scenarios passed on the baseline, so no redundant filesystem resolution is added; the key depends on this local directory, never origin.

The existing root derivation remains: a canonical common directory named `.git` yields its parent, otherwise root equals the common directory. Root does not promise a selected checkout, especially with separate metadata directories. Consumer checkout selection is separate.

## Verification

Tests first at the public surface. Real/fake scenarios cover clone separation and origin-independent local identity. Actual temporary Git repositories cover linked checkouts and symlinked common directories. Process-boundary failures prove an unreadable origin cannot become absence; no generic fake failure registry is added.

Canonicalization is verified existing behavior, not a repaired topology defect. Default memoization stays unchanged. Consumers needing current display metadata must use `RealRepo(..., memoize=False)`; identity failures are not valid absence results.

## Dependency delivery

Local wheel verification is candidate evidence only, separate from the consumer's normal locked gate. A local checkpoint is not remotely fetchable. Keep consumer integration incomplete until an explicitly authorized publication provides a portable immutable pin. Never commit absolute path overrides.

## Discovery absence classification

The affected gate exposed eight actual Git scenarios where filesystem-boundary discovery reports `fatal: not a git repository (or any parent up to mount point /)` followed by a boundary explanation. The existing library classifier recognizes only the ordinary parent-directory diagnostic. Extend its existing exit-128 absence branch to the complete mount-point diagnostic. Do not change Git discovery environment or parse diagnostics in the consumer. Table tests retain unknown, malformed and wrong-exit-code failures as `GitUnavailable`.
