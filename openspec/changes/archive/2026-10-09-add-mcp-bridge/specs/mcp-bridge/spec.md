## ADDED Requirements

### Requirement: The bridge relays a stdio client to an HTTP MCP server

`build_bridge(url, headers=…)` SHALL return a server that, served over stdio, answers each request
by relaying it to `url` over Streamable HTTP in a fresh server session, so the client sees the
remote server's tools. `headers` SHALL be sent with each relayed request; when it is a function it
SHALL be called per request, and `downstream_client_name()` SHALL return the name the stdio client
gave in its `initialize` within that call.

#### Scenario: The server's tools and the bridge's headers

- **WHEN** a client lists tools and calls one through a bridge built with `headers={"X-Token": "t1"}`
- **THEN** it sees the server's tools and the server receives `X-Token: t1`

### Requirement: A relayed call waits out a server restart

A relayed request that meets a refused connection SHALL be retried until the server accepts one,
for up to `wait` seconds, then sent; past `wait` it SHALL fail. A failure other than a refused
connection SHALL be returned at once.

#### Scenario: A call during a restart goes through

- **GIVEN** a client that has called through the bridge
- **WHEN** the server stops, the client calls again, and the server starts again 1.5 s later
- **THEN** the call returns the tool's result

#### Scenario: A server that stays down fails after the wait

- **WHEN** the server never answers and `wait` is 1 s
- **THEN** the client's connect fails after at least 1 s
