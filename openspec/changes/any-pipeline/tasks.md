# Tasks

- [ ] 1. Tests first: G1, G2, G3, G4, G5 as pyrefly-checked "must not compile" fixtures (a test runs pyrefly on a file of wrong programs and asserts each error code) and as runtime tests for the build checks.
- [ ] 2. `stage.py`: `Stage` (async fn), `Limit`, `>>`, `gather` (2-4), `blocking`; build check (limits > 0, tries >= 1, frozen input).
- [ ] 3. `outcome.py`: `Ok`, `Failed`, `Outcome`, `StageRecord`, `Report`.
- [ ] 4. `run.py`: `async run`: items under a `TaskGroup` with `workers`, branches in `TaskGroup`s, `Semaphore` per stage, `asyncio.timeout` per stage, one item never stops another, records, `Persistent` skip by key.
- [ ] 5. `preset.py` + test that each banned API is rejected (G10).
- [ ] 6. Re-express any-speech `Pipeline` on it; its tests unchanged.
- [ ] 7. README, catalog manifest, use-case file for any-speech, ledger entry, `just check`, tag `any-pipeline-v0.1.0`.
- [ ] 8. Bead `any-drain` (deferred; trigger: a second consumer of the keyed-job queue).
