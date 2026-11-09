# Ownership and behavior

`reads.TaskReadClient` contains only the existing show operation. Its positional-only
argument permits Bd's existing show(bead=...) keyword without a compatibility alias
or a method signature change. Existing Bd satisfies the protocol structurally.

`testing.FakeTaskReadClient` holds seeded Bead snapshots and persistent BdError faults
by requested ID. Each instance represents one independently configured backlog.
Unknown IDs and explicit not_found faults return None; other faults override records
and preserve diagnostics. Its read journal serves consumer assertions. It does not
run commands, interpret wire replies, register scopes or expose mutation operations.
The pure task_read_contract checks the same read rules against both the semantic fake
and real Bd with controlled Runner replies; Script remains a transport-only fixture.

`records` remains the sole decoder. Present title, description and acceptance must
be strings. Present dependencies must be an array of records, each with a nonempty
ID and relationship; their supplied text fields must also be strings. Missing
optional fields retain their empty defaults; unknown fields remain tolerated.
Relationship values are preserved, including parent-child, without an invented
allowlist. The shared parser also serves find/ready: these now refuse malformed
consumed fields consistently, while their valid records, dependency aliases and
empty-list behavior remain. Mutation methods do not use this record decoder.

`Bd.show` requires exactly one decoded row with the requested ID; [] is malformed.
`classify` recognizes complete pinned issue-absence diagnostic forms, never generic
'not found' substrings. Mixed backend/absence diagnostics remain other failures;
classification considers complete diagnostics before truncating displayed detail.
No alternate launcher, task model or error framework is introduced.
