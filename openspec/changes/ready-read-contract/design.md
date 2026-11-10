# Ownership and behavior

`reads.ReadyReadClient` contains only the existing ready operation. Its positional-only optional label lets
`Bd.ready(label="")` satisfy it structurally without a signature change.

`testing.FakeTaskReadClient(records, *, faults=None, ready=(), ready_fault=None)` keeps one seeded backlog. `ready`
names seeded record IDs in the tracker's order; an unknown or duplicate ID raises ValueError at construction, since a
ready row is one record. `ready(label)` returns deep copies of those records carrying the label (all when empty), in
seeded order. `ready_fault` fails every ready call with a fresh BdError holding its kind, text and missing sections.
Per-ID `faults` keep applying to `show` only: one ready call is one tracker read and does not consult them.
`reads` keeps recording show IDs; `ready_reads` records each ready label ("" for none). No runner, no mutation.

`ready_read_contract(make)` takes `make(records, ready_ids, ready_fault)` and checks: the tracker's order (neither ID
nor priority order), label filtering and an unmatched label as [], records outside the ready IDs absent whatever their
status, no ready IDs as [], decoded scheduling fields (priority including None, parent, assignee, sorted labels,
issue type), typed failures for malformed, missing_binary, timeout and other, and independent instances. The real
side runs `Bd` over a controlled Runner asserting `bd --actor reader ready -n 0 [--label L] --json` and the configured
cwd; it answers `{}` for malformed (a dict without `id`, which `beads_of` refuses), exit 124/127/1 for the others,
and prints nothing for an empty ready set, which `Bd._beads` already maps to [].
