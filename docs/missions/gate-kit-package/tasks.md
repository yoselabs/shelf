# Tasks: gate kit

Beads with acceptance criteria; tests first; Done = `just check` green over the whole repo. Ordering: 1-2 first; 3-5 can then proceed in parallel; 6-9 after.

- [x] 1. Owner decided the own core (2026-11-19); ADR 0021 rewritten (0004, 0023, 0027 stay).
- [~] 2. First slice built as one package, `any-gate` 0.1.0 (receipts, worker plan, staged pytest runs), on `stream-proc`, `atomic-io`, `content-digest`; the Python adapter (graph, `uv export`, selection) is its own package, `any-gate-python` 0.1.0 (shelf-3pcn.4); the core imports no adapter.
- [~] 3. Core: `changed` (shelf-3pcn.2) and the parallel `steps` runner with budgets and timing (shelf-3pcn.3) are in `any-gate`; `tools/changed.py` and its recipe copy are deleted and the justfile's `steps` recipe is a one-line call. Drift check (`preset_drift.py`) is still open: part with budgets and timing (from the `steps` recipe), changed-files listing (from `changed.py`), drift check (from `preset_drift.py`).
- [x] 4. Core: `GateState` and the verbs `start`, `passed`, `pre-push` in `any-gate` replace `gate_state.py` (shelf-3pcn.1). The shelf calls them; `tools/gate_state.py` and the blueprint `gate-state` recipe
      are deleted (the cross-package duplication rule forbids two copies). Consumers get `any-gate` as a dev dependency pinned by git tag `any-gate-v0.1.0` through onboarding; THE TAG MUST EXIST
      before a consumer is onboarded or re-onboarded. A repo with no python runs the gate hook plainly.
- [ ] 5. Core: run guard and lock/slots (see `gate-test-loop` D4); extraction reads task-loop history at 5a940722b; tests written first.
- [x] 6. Python adapter: workspace graph, `uv export` fingerprint, selection, in `any-gate-python`; `tools/affected.py` is deleted. The shelf's own path rules are `[tool.any-gate.python]` in the root pyproject.
- [ ] 7. `blueprint` CLI verbs (`check`, `test`, `render`) over the core; the guard hook entry that needs no shelf clone.
- [ ] 8. Move or declare every script in `tools/` and `recipes/` per the inventory; delete the duplicates in `recipes/`.
- [ ] 9. Shelf adopts its own packages (workspace edges); `just check` and the pre-push hook call the new verbs; remove `tools/affected.py`, `changed.py`, `gate_state.py`.
- [ ] 10. Migrate a2kay, then task-loop, then OGY (each its own session and PR in that repo; owner approves each).
- [ ] 11. Write the second adapter's capability list for .NET against `dotnet.toml` and confirm nothing in the core is Python-shaped.
- [ ] 12. `just check` green; `just check-all` once; archive.
