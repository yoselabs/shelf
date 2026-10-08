## ADDED Requirements

### Requirement: An argument-schema failure reaches the consumer as a fault

`ArgumentErrorMiddleware(render)` SHALL catch a tool call that FastMCP refuses for its arguments
(a pydantic `ValidationError`) and return `render(fault)`, where the `ArgumentFault` names the
tool, the argument (a dotted path; `arguments` when pydantic names none), pydantic's reason, and
whether the tool has no such argument (`unknown`). Every other failure, and every valid call,
SHALL pass through untouched.

#### Scenario: A missing argument is named

- **WHEN** a tool requiring `version` is called without it
- **THEN** `render` receives a fault with `argument == "version"`, `unknown == false` and no hint

#### Scenario: A tool's own failure passes through

- **WHEN** a tool called with valid arguments raises
- **THEN** `render` is not called

### Requirement: An argument the tool does not have says the tool list is stale

A fault for an argument the tool does not take SHALL be `unknown`, its message SHALL say the tool
has no such argument, and its hint SHALL tell the caller to reconnect the MCP server to refresh
its tool list. When a call has several faults, an unknown argument SHALL be the one reported. The
middleware SHALL NOT accept the argument.

#### Scenario: A client with a cached schema sends a removed argument

- **WHEN** `update` is called with `unset: null`, an argument it no longer has
- **THEN** the fault is `unknown`, names `unset`, and its hint names reconnecting (`/mcp`)

#### Scenario: The unknown argument wins

- **WHEN** a call both omits a required argument and sends one the tool does not have
- **THEN** the fault names the unknown argument
