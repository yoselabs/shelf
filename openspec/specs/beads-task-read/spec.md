## Requirements

### Requirement: A single-task read preserves identity and requirements

A successful read SHALL return exactly one matching task record with its consumed text and dependency fields preserved. Missing optional fields SHALL retain their documented empty defaults. Present malformed consumed data, malformed dependency entries, empty or multiple successful show rows, and mismatched returned identity SHALL raise the owning malformed error.

### Requirement: Missing tasks differ from unavailable backends

Only complete recognized issue-absence diagnostics SHALL return absence. Unknown backend failures, missing databases or tables, and mixed diagnostics SHALL remain typed failures with diagnostic text. Text classification remains confined to the owning CLI boundary.

### Requirement: Consumers can exercise the same read contract without a process

The owning library SHALL expose a structural single-task read protocol, a semantic in-memory read fake, and a shared success/absence/failure contract. Separate fake instances SHALL represent separate backlogs without a CLI protocol or process execution. This read API SHALL not require mutation methods or a second task model.
