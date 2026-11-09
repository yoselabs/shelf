# First-stage implementation evidence

Worktree: /home/iorlas/Workspaces/wt/shelf-git-porcelain-66.
Assigned task shelf-4426, factory consumer tl-8bh9.4.4.1. No version bump,
commit, publication, task mutation or live model invocation was performed here.

The new any-agent registration scenario was first run against the old implementation.
Its target wrote a marker and notified the FIFO while the started hook was blocked;
the test failed at `assert not readable`. The implemented gate makes it pass.

Focused package verification (Linux):

- `uv run --locked pytest packages/stream-proc/tests packages/any-agent/tests tests/test_size_caps.py -q -p no:cov`:
  715 passed, 6 skipped (actual macOS-only cases), 38.04 seconds.
- `uv run --locked pyrefly check packages/stream-proc packages/any-agent`: zero errors;
  the existing configured suppression count is unchanged in source.
- `uv run --locked ruff check packages/stream-proc packages/any-agent`: passed.
- `uv run --locked ruff format --check packages/stream-proc packages/any-agent`: passed.
- `uv run --locked codespell packages/stream-proc packages/any-agent openspec/changes/registered-process-start`: passed.
- `uv run --locked pytest tests/test_size_caps.py -q -p no:cov`: 6 passed.

Real controlled children cover registration blocking, BaseException rejection,
controller death before and after permission, deferred SIGINT/SIGTERM replay,
complete-frame versus EOF/partial/invalid/oversized/expired permission, literal argv,
exact original environment including LC_CTYPE, hostile cwd/PYTHONPATH modules,
stdin/stdout/stderr/cwd, PID/session continuity, private-FD closure, native target
startup error and postpermission uncertainty retaining identity/cause. Any-agent's
live-start failure stays behind the gate and its uncertainty preserves Worker facts
without a fabricated whole-workload-stop report. Native identity tests cover actual
Linux observations plus unreadable/malformed records, boot changes, PID/start mismatch,
and controlled macOS errno distinctions.

No actual macOS execution was available. Its native boot UUID source was checked
against Apple's kernel definition; sandbox denial remains unknown/refusal. Existing
capture/run/tree APIs remain intact. Whole-tree proof, lock lifetime, surviving
supervisor/result collection, factory integration, whole-repo gates and independent
review remain separate coordinator work; this is not a restart-safe factory claim.
