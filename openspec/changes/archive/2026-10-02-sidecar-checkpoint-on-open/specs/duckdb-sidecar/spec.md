## Purpose

How a sidecar store opens its DuckDB file, and how it recognises the two failures DuckDB reports only by message: another process holding the write lock, and an index that lost rows.

## ADDED Requirements

### Requirement: A replayed WAL is checkpointed on open

`connect()` SHALL run `CHECKPOINT` right after opening a file target, before returning the connection. It SHALL NOT for `:memory:`.

#### Scenario: Rows replayed from a WAL survive the next close
- **GIVEN** a file with an indexed table whose last insert lives only in the WAL (the writer died without checkpointing)
- **WHEN** it is opened with `connect()` and closed normally, then reopened
- **THEN** an index lookup finds the inserted rows and `DELETE FROM` the table succeeds

### Requirement: Index drift is recognisable

`is_index_drift(exc)` SHALL return true for a DuckDB error whose message holds "Failed to delete all rows from index", and false for any other exception.

#### Scenario: Drift is told apart from other errors
- **WHEN** `is_index_drift` is given that DuckDB error, a lock conflict, and a plain `ValueError` with the same text
- **THEN** it returns true, false and false
