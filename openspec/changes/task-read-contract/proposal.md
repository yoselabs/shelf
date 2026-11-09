# Truthful single-task reads

Owner: beads-client. Task: shelf-ryf2; consumer plan:
`iorlas-task-loop/docs/design/tl-8bh9.6.2.1/plan.md`.

Factory inspection needs the existing Bd.show operation with an owning semantic
fake. Add a structural read-only protocol without requiring writes, a second task
model, another runner, scope discovery or task-spec adoption. The factory remains
responsible for explicit tracker/backlog binding and its application projection.

A malformed read must not become absence, erased requirements or dropped
dependencies. Retain valid existing records, omitted optional defaults, dependency
aliases and relationship values. Release and consumer pinning are separate owner
operations; this change does not bump versions or claim a release.
