# a2kay's expired coverage override (task 10)

Checked 2026-11-20, read-only (`blueprint check --repo ~/Workspaces/a2kay --gate` and `--json`; nothing written, nothing changed there).

- Override: `stack.python-uv.coverage` (code `not-detected`), `expires = 2026-11-11`, so expired 9 days ago.
- What a2kay's `just blueprint` step shows with the shelf main checkout: `69/86 passing`, exit 0. No line about the override.
- Why it stays green: the override is moot. The checkpoint now passes on its own ("coverage.py's `coverage report --fail-under=<N>`, run by the
  gate"; shelf-2hl taught it that floor). An expired override only stops excusing a row that fails, so nothing turned red.
- The silence is the defect the owner named: the expiry passed unnoticed and a dead override stays in the file.
- With task 9's notice the same step prints `blueprint: warning: override stack.python-uv.coverage expired 2026-11-11: ...`, still exit 0.
- Follow-up for a2kay's owner (not done here, a2kay is read-only for this task): delete that override.

Open: the notice names any expired override, including one whose checkpoint already passes. That is intended (a dead override is clutter), but
it means a consumer sees the warning until it deletes the entry.
