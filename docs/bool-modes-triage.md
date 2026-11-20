# Bool-mode triage (shelf-cypc follow-up)

Input: the `mode:` and `fact:` rows of `tests/test_arch_bool_modes.py` (Article III, no optionality; ADR 0022 for exceptions).
Method: each row read in its code, not from the old reason. Verdicts:

- **A** split: the flag picks between two behaviours of one operation; the proposal names the separate type or function.
- **B** fact: data about a call, a value or an error, or a third-party library's own option; not a code path.
- **C** cost opt-in or construction config (Article IX): the default is the complete or durable answer and the flag skips or adds one named cost, or is chosen once at construction; kept as a row, ADR 0030. The tolerance and destructive C rows (`missing_ok`, `force`, `allow_delete`, `ignored`, `nested`, `allow_empty`, `hooks`, `keep_ignored`, `any_replica`) were debt, converted in shelf-tyld.26 (ADR 0030 rewritten) and are deleted from this table.
- **FIXED**: an A row private to one package with no external consumer, cheap and test-covered; fixed in this change.

Counts: 114 rows at the start. FIXED 41 (4 earlier + 37 split in shelf-tyld.13); A left 1 (blueprint:run:audit, skipped); B 44; C 8 kept here (fsync x4, with_dirty, check_push, memoize, pin; the `atomic_replace_*` and `try_run` repeats are the rest); 20 tolerance and destructive C rows converted to exceptions and verbs in shelf-tyld.26. Rows added by new split functions: `atomic_replace_*` repeat the `fsync` (C) and `sort_keys` (B) rows, `try_run` repeats `pin` (C).

External consumers (a2kay, a2web, ogy, iorlas-*) are not in this tree: the splits below break their calls (major/minor bump + CHANGELOG each).

| row | verdict | proposal / reason |
|---|---|---|
| `jsonl-log:_drop:evict` | FIXED (A) | `_close(key)` and `_evict(key)` on HeldLogs (jsonl-log 0.5.0) |
| `shelf-vendor:_say:err` | FIXED (A) | `_out(text)` and `_err(text)` (shelf-vendor 0.3.0) |
| `blueprint:write:prune` | FIXED (A) | `report.write` always writes; `report.prune_stale(repo, written)` is called by the CLI after a full run (blueprint 0.2.0) |
| `blueprint:write:executable` | FIXED (A) | `Repo.write` and `Repo.write_executable` in `blueprint.testing` (blueprint 0.2.0) |
| `any-browser:_navigate:scroll_to_stable` | FIXED (A) | split in any-browser 0.3.0: `render` and `render_listing` on the Backend protocol |
| `any-browser:render:scroll_to_stable` | FIXED (A) | split in any-browser 0.3.0: `render` and `render_listing` on the Backend protocol |
| `anyllm:resolve_provider:fallback` | FIXED (A) | split in anyllm 0.11.0: `resolve_provider` and `resolve_first` |
| `app-dirs:cache_dir:create` | FIXED (A) | split in app-dirs 0.3.0: pure `*_dir`, `plugin_dir(kind, app)`, `ensure(path)` |
| `app-dirs:cache_dir:plugin_data` | FIXED (A) | split in app-dirs 0.3.0: pure `*_dir`, `plugin_dir(kind, app)`, `ensure(path)` |
| `app-dirs:config_dir:create` | FIXED (A) | split in app-dirs 0.3.0: pure `*_dir`, `plugin_dir(kind, app)`, `ensure(path)` |
| `app-dirs:config_dir:plugin_data` | FIXED (A) | split in app-dirs 0.3.0: pure `*_dir`, `plugin_dir(kind, app)`, `ensure(path)` |
| `app-dirs:data_dir:create` | FIXED (A) | split in app-dirs 0.3.0: pure `*_dir`, `plugin_dir(kind, app)`, `ensure(path)` |
| `app-dirs:data_dir:plugin_data` | FIXED (A) | split in app-dirs 0.3.0: pure `*_dir`, `plugin_dir(kind, app)`, `ensure(path)` |
| `app-dirs:state_dir:create` | FIXED (A) | split in app-dirs 0.3.0: pure `*_dir`, `plugin_dir(kind, app)`, `ensure(path)` |
| `app-dirs:state_dir:plugin_data` | FIXED (A) | split in app-dirs 0.3.0: pure `*_dir`, `plugin_dir(kind, app)`, `ensure(path)` |
| `atomic-io:atomic_write_bytes:keep_mode` | FIXED (A) | split in atomic-io 0.3.0: `atomic_write_*` (0o600) and `atomic_replace_*` (keeps the replaced file's mode) |
| `atomic-io:atomic_write_json:keep_mode` | FIXED (A) | split in atomic-io 0.3.0: `atomic_write_*` (0o600) and `atomic_replace_*` (keeps the replaced file's mode) |
| `atomic-io:atomic_write_text:keep_mode` | FIXED (A) | split in atomic-io 0.3.0: `atomic_write_*` (0o600) and `atomic_replace_*` (keeps the replaced file's mode) |
| `blueprint:run:audit` | A | `run_gate(repo)` and `run_audit(repo)` sharing `_judge`; the CLI picks one. Private to the shelf (use-case shelf--blueprint) but touches the CLI, skill docs and ~20 tests. Skipped by the owner brief (blueprint was handled separately). |
| `child-env:scrub:strip_venv` | FIXED (A) | split in child-env 0.3.0: `scrub(without_venv(env))` (venv stripped first, same result) |
| `child-env:scrub_current:strip_venv` | FIXED (A) | split in child-env 0.3.0: `scrub(without_venv(env))` (venv stripped first, same result) |
| `convert-md:_result:check_yield` | FIXED (A) | split in convert-md 0.12.0: `grade` and `grade_container` (the structure check still reads the size, so `None` was wrong) |
| `convert-md:grade:check_yield` | FIXED (A) | split in convert-md 0.12.0: `grade` and `grade_container` (the structure check still reads the size, so `None` was wrong) |
| `git-porcelain:continue_rebase:check_markers` | FIXED (A) | split in git-porcelain 0.26.0: `resolve_and_continue()` |
| `git-porcelain:continue_rebase:stage_conflicts` | FIXED (A) | split in git-porcelain 0.26.0: `resolve_and_continue()` |
| `git-porcelain:fetch:retry` | FIXED (A) | split in git-porcelain 0.26.0: `fetch` and `fetch_once` (fake) |
| `git-porcelain:memo:forever` | FIXED (A) | split in git-porcelain 0.26.0: `memo` and `memo_until_write` |
| `git-porcelain:remote_url:push` | FIXED (A) | split in git-porcelain 0.26.0: `remote_url` and `remote_push_url` |
| `git-porcelain:remote_urls:push` | FIXED (A) | split in git-porcelain 0.26.0: `remote_urls` and `remote_push_urls` |
| `git-porcelain:run:check` | FIXED (A) | split in git-porcelain 0.26.0: `run` and `try_run` |
| `git-porcelain:run_git:check` | FIXED (A) | split in git-porcelain 0.26.0: `run_git` and `try_git` |
| `git-porcelain:stage:literal` | FIXED (A) | split in git-porcelain 0.26.0: `stage` and `stage_pathspec` |
| `jsonl-log:__init__:read_only` | FIXED (A) | split in jsonl-log 0.6.0: `JsonlReader` beside `JsonlLog` |
| `jsonl-log:open:read_only` | FIXED (A) | split in jsonl-log 0.6.0: `JsonlReader` beside `JsonlLog` |
| `llm-wobble:parse_list_with_policy:strip_fences` | FIXED (A) | split in llm-wobble 0.6.0 |
| `llm-wobble:strip_fenced_blocks:json_only` | FIXED (A) | split in llm-wobble 0.6.0 |
| `process-lock:acquire:reentrant` | FIXED (A) | split in process-lock 0.4.0: `acquire` and `acquire_exclusive` |
| `sqlite-sidecar:connect:read_only` | FIXED (A) | split in sqlite-sidecar 0.4.0: `connect_read_only`, `from_text_utc` |
| `sqlite-sidecar:from_text:aware` | FIXED (A) | split in sqlite-sidecar 0.4.0: `connect_read_only`, `from_text_utc` |
| `stream-proc:_hit:group` | FIXED (A) | split in stream-proc 0.11.0 |
| `stream-proc:capture_bytes:capture` | FIXED (A) | split in stream-proc 0.11.0 |
| `verb-cli:flags_of:choices` | FIXED (A) | split in verb-cli 0.3.0: `flags_of` and `choice_flags_of` |
| `any-json-doc:__init__:fsync` | C | KEPT: cost opt-in, Article IX: the default is the complete or durable answer; the flag skips or adds one named cost (ADR 0030) |
| `atomic-io:atomic_write_bytes:fsync` | C | KEPT: cost opt-in, Article IX: the default is the complete or durable answer; the flag skips or adds one named cost (ADR 0030) |
| `atomic-io:atomic_write_json:fsync` | C | KEPT: cost opt-in, Article IX: the default is the complete or durable answer; the flag skips or adds one named cost (ADR 0030) |
| `atomic-io:atomic_write_text:fsync` | C | KEPT: cost opt-in, Article IX: the default is the complete or durable answer; the flag skips or adds one named cost (ADR 0030) |
| `git-porcelain:__init__:memoize` | C | KEPT: construction config, chosen once when the object is built (ADR 0030) |
| `git-porcelain:readiness:check_push` | C | KEPT: cost opt-in, Article IX: the default is the complete or durable answer; the flag skips or adds one named cost (ADR 0030) |
| `git-porcelain:run:pin` | C | KEPT: cost opt-in, Article IX: the default is the complete or durable answer; the flag skips or adds one named cost (ADR 0030) |
| `git-porcelain:worktrees:with_dirty` | C | KEPT: cost opt-in, Article IX: the default is the complete or durable answer; the flag skips or adds one named cost (ADR 0030) |
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

## Outcome

- Every A row except the blueprint one is split. The four git-porcelain `missing_ok` rows, once reclassified as a justified tolerance, are converted: `drop_worktree` raises `NotAWorktree`, `abort_rebase` is idempotent, `delete_remote_at` raises on refusal, `continue_rebase` returns `ok=False`.
- The 2026-11-20 policy check (`policy_params` in the arch test) also lists public `Literal`/Enum parameters: `debt:` rows there (`record(mode=)`, `finish_rebase(action=)`, `rebase_onto(squash_failure=)`, `take_branch(mode=)`, any-markdown `anchors`, page-tsv `consumer`, blueprint `scan(mode=)`) are the next conversions.
- Two triage proposals were wrong and changed: `convert-md` `grade(source_size=None)` would also have switched off the structure check, so it is `grade` and `grade_container`; `child-env` composes as `scrub(without_venv(env))` (venv first), which needs no `venv=` argument.
- `git-porcelain` `continue_rebase(stage_conflicts, check_markers)` became `resolve_and_continue()` (both together, the only combination any caller used).
