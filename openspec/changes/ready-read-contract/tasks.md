# Tasks

- [x] `ReadyReadClient` protocol in `reads.py`, exported from `beads_client`.
- [x] `FakeTaskReadClient(ready=, ready_fault=)`, `ready()` and `ready_reads`; construction refuses unknown or duplicate ready IDs.
- [x] `ready_read_contract` in `testing.py`; `tests/test_ready_read.py` runs it against `Bd` (controlled Runner) and the fake, plus fake-only cases.
- [x] CONTRACT, README, CHANGELOG; version 0.2.0; catalog release; ledger delivery.
- [ ] Owner: review, merge to main, annotated tag `beads-client-v0.2.0`, push the tag.
- [ ] Consumer: pin `beads-client==0.2.0` at the tag and record the adoption verdict.
