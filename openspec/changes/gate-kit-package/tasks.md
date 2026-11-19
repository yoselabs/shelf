# Tasks: gate kit

Beads with acceptance criteria; tests first; Done = `just check` green over the whole repo. Ordering: 1-2 first; 3-5 can then proceed in parallel; 6-9 after.

- [x] 1. Owner decided the own core (2026-11-19); ADR 0021 rewritten (0004, 0023, 0027 stay).
- [ ] 2. Pick the package names (`pick-name`); fix the split (one package or core plus adapters) after reading how coupled receipts and the guard are.
- [ ] 3. Core: parallel step runner with budgets and timing (from the `steps` recipe), changed-files listing (from `changed.py`), drift check (from `preset_drift.py`).
- [ ] 4. Core: receipts and ledger; replace `gate_state.py`; shared by hooks and manual runs (see `gate-test-loop` D3).
- [ ] 5. Core: run guard and lock/slots (see `gate-test-loop` D4); extraction reads task-loop history at 5a940722b; tests written first.
- [ ] 6. Python adapter: workspace graph, `uv export` fingerprint, pytest runner, selection; replaces `tools/affected.py`.
- [ ] 7. `blueprint` CLI verbs (`check`, `test`, `render`) over the core; the guard hook entry that needs no shelf clone.
- [ ] 8. Move or declare every script in `tools/` and `recipes/` per the inventory; delete the duplicates in `recipes/`.
- [ ] 9. Shelf adopts its own packages (workspace edges); `just check` and the pre-push hook call the new verbs; remove `tools/affected.py`, `changed.py`, `gate_state.py`.
- [ ] 10. Migrate a2kay, then task-loop, then OGY (each its own session and PR in that repo; owner approves each).
- [ ] 11. Write the second adapter's capability list for .NET against `dotnet.toml` and confirm nothing in the core is Python-shaped.
- [ ] 12. `just check` green; `just check-all` once; archive.
