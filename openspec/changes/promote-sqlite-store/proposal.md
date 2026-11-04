## Why

Task-loop's factory database mixes reusable SQLite-on-disk safety with application
schema and queries. Its connection ownership, WAL configuration, filesystem checks,
transaction and migration behavior already have a consumer-proven shape.

## What Changes

Add the stdlib-only, POSIX-only `sqlite-store` primitive, born candidate. Extract
the generic lifecycle into schema-parameterized functions and a Store. Keep every
application table, owner policy and query in task-loop. Add plain pytest contracts,
package documentation, the catalog manifest and task-loop's use case.

## Impact

New `packages/sqlite-store` distribution at 0.1.0, intended release
`sqlite-store-v0.1.0`. The owner validates and handles consumer adoption, generated
indexes, lockfile refresh and release; this extraction does not edit the source copies.
