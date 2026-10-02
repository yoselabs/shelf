## Context

DuckDB issue #26106: rows restored by WAL replay go missing from ART indexes at the next shutdown or automatic checkpoint; an explicit `CHECKPOINT` after replay is correct. Upstream fix pending (#23848 unmerged; 2.0 nightly fixes only the shutdown path).

## Goals / Non-Goals

**Goals:** no sidecar opened through `connect()` can persist a drifted index from a replayed WAL; a consumer can recognise drift that is already on disk.
**Non-Goals:** repairing a drifted file (drop/recreate cannot fix PK/UNIQUE indexes; consumers rebuild derived stores); fewer unclean exits (each consumer's process management).

## Decisions

- **Checkpoint on open, not on close.** Close already checkpoints — that is the buggy path. The explicit checkpoint has to be the first one after replay.
- **Classifier by message substring**, like `is_lock_conflict`: DuckDB reports it as `InvalidInputException` / `FatalException` with no dedicated type. Narrow: only DuckDB `Error` subclasses whose message carries "Failed to delete all rows from index".

## Risks / Trade-offs

- [Open is slower when a large WAL exists] → that work happens at the next checkpoint anyway; it moves earlier, it is not added.
- [A read-only connection cannot checkpoint] → `connect()` opens read-write only; unchanged.
