# Bool-mode triage (shelf-cypc follow-up)

Input: the `mode:` and `fact:` rows of `tests/test_arch_bool_modes.py` (Article III, no optionality; ADR 0022 for exceptions).
Method: each row read in its code, not from the old reason. Verdicts:

- **A** split: the flag picks between two behaviours of one operation; the proposal names the separate type or function.
- **B** fact: data about a call, a value or an error, or a third-party library's own option; not a code path.
- **C** exception: Article IX allows a flag that opts into a cost, and a named safety or durability opt-in is the default-safe pit of success; kept as a justified row, each needing an accepted ADR (0022) to be durable.
- **FIXED**: an A row private to one package with no external consumer, cheap and test-covered; fixed in this change.

Counts: 114 rows. FIXED 4; A (left) 42; B 44; C 24.

External consumers (a2kay, a2web, ogy, iorlas-*) are not in this tree: an A row on a public export or with a `use-cases/` row from one of them is left, with the consumers named. git-porcelain (public `Repo` protocol, consumed by ogy and a2kay) is classified only.

| row | verdict | proposal / reason |
|---|---|---|
| `shelf-vendor:_say:err` | FIXED (A) | `_out(text)` and `_err(text)` (shelf-vendor 0.3.0) |
| `blueprint:write:prune` | FIXED (A) | `report.write` always writes; `report.prune_stale(repo, written)` is called by the CLI after a full run (blueprint 0.2.0) |
| `blueprint:write:executable` | FIXED (A) | `Repo.write` and `Repo.write_executable` in `blueprint.testing` (blueprint 0.2.0) |
| `atomic-io:atomic_write_bytes:keep_mode` | A | Pick ONE behaviour for a replaced file (keep its bits; new file 0o600) and delete the flag, or add `atomic_write_keeping_mode`. Four consumers. Left: touches stored file permissions (needs an owner call). |
| `atomic-io:atomic_write_json:keep_mode` | A | Pick ONE behaviour for a replaced file (keep its bits; new file 0o600) and delete the flag, or add `atomic_write_keeping_mode`. Four consumers. Left: touches stored file permissions (needs an owner call). |
| `atomic-io:atomic_write_text:keep_mode` | A | Pick ONE behaviour for a replaced file (keep its bits; new file 0o600) and delete the flag, or add `atomic_write_keeping_mode`. Four consumers. Left: touches stored file permissions (needs an owner call). |
| `blueprint:run:audit` | A | `run_gate(repo)` and `run_audit(repo)` sharing `_judge`; the CLI picks one. Private to the shelf (use-case shelf--blueprint) but touches the CLI, skill docs and ~20 tests. Left: not cheap. |
| `git-porcelain:abort_rebase:missing_ok` | A | Return a `Missing`/`Gone` outcome value and let the caller decide, instead of `missing_ok`. git-porcelain public Repo protocol (ogy consumes). Not touched. |
| `git-porcelain:continue_rebase:check_markers` | A | `resolve_and_continue(...)` beside `continue_rebase()`. git-porcelain public Repo protocol (ogy consumes). Not touched. |
| `git-porcelain:continue_rebase:missing_ok` | A | Return a `Missing`/`Gone` outcome value and let the caller decide, instead of `missing_ok`. git-porcelain public Repo protocol (ogy consumes). Not touched. |
| `git-porcelain:continue_rebase:stage_conflicts` | A | `resolve_and_continue(...)` beside `continue_rebase()`. git-porcelain public Repo protocol (ogy consumes). Not touched. |
| `git-porcelain:delete_remote_at:missing_ok` | A | Return a `Missing`/`Gone` outcome value and let the caller decide, instead of `missing_ok`. git-porcelain public Repo protocol (ogy consumes). Not touched. |
| `git-porcelain:drop_worktree:missing_ok` | A | Return a `Missing`/`Gone` outcome value and let the caller decide, instead of `missing_ok`. git-porcelain public Repo protocol (ogy consumes). Not touched. |
| `git-porcelain:fetch:retry` | A | `fetch` and `fetch_once` in fake_flow (the real fetch has no such flag). Fake internals. Not touched (git-porcelain). |
| `git-porcelain:memo:forever` | A | `memo` and `memo_until_write`. RealRepo internals. Not touched (git-porcelain). |
| `git-porcelain:remote_url:push` | A | `remote_url` and `remote_push_url` (and plural forms). git-porcelain public Repo protocol. Not touched. |
| `git-porcelain:remote_urls:push` | A | `remote_url` and `remote_push_url` (and plural forms). git-porcelain public Repo protocol. Not touched. |
| `git-porcelain:run:check` | A | `run` (raises) and `try_run` (returns `Done`). git-porcelain internal runner, 40+ call sites. Not touched (git-porcelain). |
| `git-porcelain:run_git:check` | A | `run` (raises) and `try_run` (returns `Done`). git-porcelain internal runner, 40+ call sites. Not touched (git-porcelain). |
| `git-porcelain:stage:literal` | A | `stage(paths)` literal and `stage_pathspec(patterns)`. git-porcelain public Repo protocol. Not touched. |
| `stream-proc:_hit:group` | A | `_hit_pid` and `_hit` (group, then pid). Private to stream-proc, but it is the signal path that kills process trees; left for an owner-reviewed change, not a drive-by. |
| `stream-proc:capture_bytes:capture` | A | `run_inherited(argv, timeout=...) -> int` beside `capture_bytes`. In-tree: any-proc, any-speech, delegate; external: a2kay. Left: external consumer. |
| `verb-cli:flags_of:choices` | A | Make argparse choices the only behaviour (a major bump) or add `choice_flags_of`. ogy (use-cases/ogy--verb-cli). Left: external consumer. |
| `any-json-doc:__init__:fsync` | C | Cost opt-in per Article IX: the default is durable, opting out is named. Needs an accepted ADR (0022) to be durable. |
| `atomic-io:atomic_write_bytes:fsync` | C | Cost opt-in per Article IX: the default is durable, opting out is named. Needs an accepted ADR (0022) to be durable. |
| `atomic-io:atomic_write_json:fsync` | C | Cost opt-in per Article IX: the default is durable, opting out is named. Needs an accepted ADR (0022) to be durable. |
| `atomic-io:atomic_write_text:fsync` | C | Cost opt-in per Article IX: the default is durable, opting out is named. Needs an accepted ADR (0022) to be durable. |
| `beads-client:reclaim:any_replica` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `beads-client:unclaim:force` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:__init__:memoize` | C | Object configuration (injected once), not a per-call branch. Needs an accepted ADR (0022). |
| `git-porcelain:add_worktree:force` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:clean:ignored` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:clean:nested` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:drop_worktree:force` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:park:keep_ignored` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:push_refspecs:allow_delete` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:push_refspecs:force` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:push_request:allow_delete` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:push_request:force` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:readiness:check_push` | C | Article IX cost opt-in. Needs an accepted ADR (0022). |
| `git-porcelain:record:allow_empty` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:record:hooks` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:run:pin` | C | Internal runner opt-out; folds into the `run`/`try_run` split when git-porcelain is next opened. |
| `git-porcelain:validate_push:allow_delete` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:validate_push:force` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:worktree_add:force` | C | Destructive-intent opt-ins mirroring `--force`, `--allow-empty`, `--no-verify`, `clean -x/-ff`, `--any-replica`; the pit of success is the default. One ADR can name the class. Needs an accepted ADR (0022). |
| `git-porcelain:worktrees:with_dirty` | C | Article IX allows a flag that asks for a costly capability. Needs an accepted ADR (0022). |
| `a2effect:__init__:retryable` | B | Data on the error value. |
| `a2effect:__init_subclass__:abstract` | B | Test-support opt-ins mirroring pytest's signature (`raising`) or selecting contract checks. |
| `a2effect:contract_tests:dead_enricher` | B | Test-support opt-ins mirroring pytest's signature (`raising`) or selecting contract checks. |
| `a2effect:contract_tests:envelope_round_trip` | B | Test-support opt-ins mirroring pytest's signature (`raising`) or selecting contract checks. |
| `a2effect:contract_tests:surface_parity` | B | Test-support opt-ins mirroring pytest's signature (`raising`) or selecting contract checks. |
| `a2effect:register_error_kind:retryable` | B | Data on the error value. |
| `any-agent:classify:timed_out` | B | Classifier input. |
| `any-agent:classify:work_seen` | B | Classifier input. |
| `any-agent:finish:killed` | B | Classifier input. |
| `anyembed:__init__:gpu` | B | Backend construction config, injected once, never branched on per call. |
| `anyembed:__init__:offline` | B | Backend construction config, injected once, never branched on per call. |
| `anyllm:__init__:retryable` | B | Data on the error value. |
| `anyllm:complete:thinking_disabled` | B | Per-call request data; every provider receives it as an argument. |
| `anyllm:delenv:raising` | B | Test-support opt-ins mirroring pytest's signature (`raising`) or selecting contract checks. |
| `anyllm:setattr:raising` | B | Test-support opt-ins mirroring pytest's signature (`raising`) or selecting contract checks. |
| `atomic-io:atomic_write_json:sort_keys` | B | Output formatting of the JSON text; same bytes written either way for a given setting. |
| `beads-client:find:include_closed` | B | Filter, not a behaviour: closed beads are in the result or not. |
| `blueprint:check:audit_only` | B | Registration metadata; the runner filters on it. The two registrars share one field. |
| `blueprint:check_each:audit_only` | B | Registration metadata; the runner filters on it. The two registrars share one field. |
| `blueprint:not_checked:blueprint_gap` | B | Data on the Finding. |
| `content-extract:_extract_sync:include_comments` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `content-extract:_extract_sync:include_links` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `content-extract:_extract_sync:include_tables` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `content-extract:extract_markdown:include_comments` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `content-extract:extract_markdown:include_links` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `content-extract:extract_markdown:include_tables` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `convert-md:_extract_trafilatura:include_comments` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `convert-md:_extract_trafilatura:include_links` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `convert-md:_extract_trafilatura:include_tables` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `convert-md:convert_html:include_comments` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `convert-md:convert_html:include_links` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `convert-md:convert_html:include_tables` | B | Data forwarded to trafilatura (`include_comments/links/tables`); the three together are a region selection. Later: one frozen `Regions` value instead of three bools (a2web is the consumer). |
| `git-porcelain:__init__:retryable` | B | Data on the error value. |
| `git-porcelain:delenv:raising` | B | Test-support opt-ins mirroring pytest's signature (`raising`) or selecting contract checks. |
| `git-porcelain:failure:retryable` | B | Data on the error value. |
| `git-porcelain:rebase:update_refs` | B | Passthrough of `rebase --update-refs/--no-update-refs`. |
| `git-porcelain:rebase_onto:update_refs` | B | Passthrough of `rebase --update-refs/--no-update-refs`. |
| `git-porcelain:start_rebase:update_refs` | B | Passthrough of `rebase --update-refs/--no-update-refs`. |
| `git-porcelain:unavailable:full_output` | B | Message rendering for one failure; the error carries `output` either way. |
| `launchd-agent:render_plist:keep_alive` | B | launchd plist keys, serialised as given. |
| `launchd-agent:render_plist:run_at_load` | B | launchd plist keys, serialised as given. |
| `sqlite-store:_open:shared` | B | sqlite3's own parameter, inverted. Private function, one call site passes True. |
| `stream-proc:popen_registered:start_new_session` | B | Passthrough of Popen's parameter. |
| `stream-proc:report:error` | B | Data on the report value. |

## What the A rows say

- Read-only vs read-write is a type difference in four places (`jsonl-log`, `sqlite-sidecar`, `process-lock`'s reentrancy, `any-browser`'s listing render): split by type, not flag.
- `app-dirs` `create` and `plugin_data` (8 rows) and `child-env` `strip_venv` (2 rows) are the cheapest public splits (app-dirs done in 0.3.0: pure lookups, `plugin_dir`, `ensure`).
- git-porcelain's 38 rows are mostly git's own flags (`force`, `allow_empty`, `clean -x`): one ADR for the destructive-opt-in class closes the C rows; the A rows (`missing_ok`, `run(check=)`, `literal`, `push`) wait for the next change that opens that package.
- ADR 0022 as written covers blueprint.toml overrides; the C rows need either an accepted ADR naming this allowlist class or an `expires` date. Not decided here.
