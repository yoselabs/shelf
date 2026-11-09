# Acquisition ownership regression evidence

Task shelf-7c34. Base824040758e5dd44c751483adcfc3f542059338b7, the delivered registered-start squash.
No registered-start behavior was changed. This branch is process-lock-acquisition-failure only.

Red before implementation: public acquire raised at post-flock metadata serialization,
native pwrite and ftruncate, registry construction and KeyboardInterrupt, but a real
independent contender remained refused. A foreign-holder pread failure separately
left its captured temporary FD open. Six cases demonstrated the bug; cleanup matched
captured FDs to the test-owned inode and removed no foreign work or child.

Green after one protected descriptor ownership region through registry adoption:

- `uv run --locked pytest packages/process-lock/tests tests/test_size_caps.py tests/test_catalog_projection.py -q -p no:cov`:
  32 passed in 8.76s, including existing real process/thread/reentrant/non-inheritable behavior.
- `uv run --locked pyrefly check packages/process-lock`: zero errors.
- Package Ruff, formatting, spelling and unchanged caps passed.
- `uv lock` and `just catalog` regenerated candidate0.2.1 metadata and projections normally.

The native probe has a finite timeout. Each failure preserves its original exception,
leaves no registry entry or leaked descriptor, and permits a real later acquisition.
A refused metadata-read failure never bypasses the live holder; a contender succeeds
only after that holder releases. Successful acquisition still transfers ownership to
the existing registry and releases only at its final reference.

Final required Linux gates are run against the checkpoint and captured in external
verification logs; their exact results/head/tree belong in the handoff. Independent
review and final-tree native verification remain required before publication. No
remote writes, tags, release or user-plugin installation occurred. This patch adds
no descendant custody, inherited-lock handoff or full restart guarantee.
