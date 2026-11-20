# Changelog

## 0.9.0

- **Breaking: `secret_scan.scan(repo, mode)` and `Mode` are gone.** `scan_staged(repo)`, `scan_range(repo)` and `scan_full(repo)` are the three scans; `python -m blueprint.secret_scan staged|range|full` is unchanged.

## 0.8.0

- **Breaking: `runner.run` lost its `audit` flag.** `run(...)` is the per-commit gate, `run_audit(...)` also runs the audit-only checks (the CLI picks one by `--audit`). What is checked and rendered is unchanged.
- **Breaking: `report.write` lost its `prune` flag.** `write(...)` prunes the reports of a concern the run no longer has, `write_concern(...)` (a one-concern run) leaves the others. Written files are unchanged.
- Test helper `Repo.write(..., executable=True)` is now `Repo.write_executable(...)`.
- Every text read and write carries `encoding="utf-8"`; every `errors="replace"` carries a `# lossy-ok:` marker; globs that feed output are wrapped in `sorted()`. No output changes on a UTF-8 machine.
- `secret_scan` and `guard`: every child process has a timeout (a hang is `ScanError`, or exit 2 for the guard, never a pass); `secret_scan` no longer reads `os.environ` or calls `shutil.which` (a missing gitleaks is the same `ScanError` message).
- Left alone on purpose: the engine is stdlib only (it runs from a bare clone on `PYTHONPATH`, README), so it does not use stream-proc, child-env, content-digest or any-clock.
