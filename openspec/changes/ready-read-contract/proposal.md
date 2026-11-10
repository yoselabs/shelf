# The ready set as an owning read seam

Owner: beads-client. Consumer request: `iorlas-task-loop/docs/design/tl-8bh9.4.3.1.13/shelf-request.md`
(scheduling plan `tl-8bh9.4.3.1.13`, `tl plan next`).

The factory's scheduling round reads the tracker's ready set once per round through the existing `Bd.ready(label)`
and needs a shared fake from the owning library. 0.1.0 exposes `TaskReadClient` for `show` only. Add a structural
`ReadyReadClient` for the existing `ready` read, extend `FakeTaskReadClient` with a seeded ready set and a whole-read
fault, and a shared `ready_read_contract` run against both `Bd` and the fake.

Readiness stays bd's computed fact: the fake seeds which records are ready and in which order, never computes it.
Additive: no existing signature changes. Version 0.1.0 -> 0.2.0; tagging and consumer pinning are separate owner steps.
