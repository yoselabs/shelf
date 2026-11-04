# any-plugin-cache

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

`installs(claude_dir, plugin, marker)` -> `{version: dir}` of complete cache dirs; `installed_version` reads the user-scope record;
`pin_ok` (a pin names an installed dir), `previous` (rollback target: newest install below current), `behind`;
`set_json_version(text, new, after=0)` and `entry_offset(text, name)` change one version and nothing else.

Executable acceptance: `tests/test_installs.py`, `tests/test_jsonver.py` over a temp claude dir, and
`tests/test_boundary_any_plugin_cache.py` (stdlib only, no consumer imported).
