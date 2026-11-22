---
id: 0032
title: Local serving belongs to one held service
statement: Group local ASGI access, readiness, serving and discovery in any-local-service; reuse token and scope primitives and keep consumer policy in the apps.
concerns: [packaging]
status: proposed
decided_by: owner
updated: 2026-11-22
distilled_into: N/A — enforced by packages/any-local-service/tests and the declared import graph
---

The owner requested one package for API and local web-serving substrate. `LocalService`
is the thing a consumer holds: its guarded ASGI app, readiness and serving lifetime.
`any-local-service` names that domain, following ADR 0015. Concern modules remain
composable for a2kay's boot path; application routes and MCP construction stay injected.

Reuse `asgi-token-gate`, `async-scope` and `atomic-io`. The lifecycle defect exposed by
the extraction is fixed in async-scope, rather than copied into another server owner.

Rejected alternatives:

- Several new micro packages: fragments the one service domain the owner asked to group.
- A library-specific extras package: names implementation details and loses the held service.
- Fold the inspection API into the package: introduces consumer domain policy.

## History

- 2026-11-22: Proposed the extracted boundary for review; the owner's grouping instruction
  establishes scope, while this ADR records the concrete shape.
