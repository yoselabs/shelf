# any-plugin-cache

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

`installs(claude_dir, plugin, marker)` -> `{version: dir}` of complete cache dirs; `installed_version` reads the user-scope record;
a pin is valid when its version is in `installs(...)` (`in`, no function); `previous` (newest install below current), `rollback_target(found, pinned, installed)` -> `(version, why)`, `behind`; `marker` may be a tuple (all must exist);
`set_json_version(text, new, after=0)` and `entry_offset(text, name)` change one version and nothing else.

Limits: `set_json_version` is a regex text edit (handles escaped quotes, not a parser); `entry_offset` takes the first `"name": "<name>"` anywhere in the text, so a same-named owner/author block misleads it.

Executable acceptance: `tests/test_installs.py`, `tests/test_jsonver.py` over a temp claude dir, and
`tests/test_boundary_any_plugin_cache.py` (stdlib only, no consumer imported).
