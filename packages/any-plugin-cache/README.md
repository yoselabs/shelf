# any-plugin-cache

What Claude Code has installed of a plugin, which of those a pin may name, where a rollback lands, and a version bump for
`plugin.json` / `marketplace.json` that leaves every other byte alone. Stdlib only; imports no host. The claude dir is a
parameter, so tests (and callers) never need the real `~/.claude`.

```python
from pathlib import Path
from any_plugin_cache import installs, installed_version, rollback_target, set_json_version, entry_offset

claude = Path.home() / ".claude"
found = installs(claude, "iorlas-task-loop", (".claude-plugin/plugin.json", "skills/task-loop/tl.py"))   # {"0.23.328": Path(...)}
cur = installed_version(claude, "iorlas-task-loop")                      # "" when unrecorded
"0.23.300" in found                                                       # a pin must name an installed dir
rollback_target(found, installed=cur)                                     # ("0.23.327", "") or ("", why)

text = set_json_version(text, "0.24.0", after=entry_offset(text, "iorlas-task-loop") or 0)
```

| function | answers |
|---|---|
| `installs` | `{version: dir}` under `plugins/cache/*/<plugin>/`; dirs lacking any `marker` file and non-version names are skipped; `plugin` is a literal name |
| `installed_version` | the user-scope version in `installed_plugins.json`, `""` on any miss |
| `previous` | newest install strictly below `current`, `""` when none or `current` is not a version |
| `rollback_target` | `(version, why)`: previous of the current one (pin, else recorded, else newest) |
| `behind` | how many installs are newer than `version` |
| `version_key` | dotted ints as an orderable tuple, `None` for anything else |
| `set_json_version` / `entry_offset` | regex edit of one `"version"`; raises `NoVersion` when absent |

Not here: where the pin is stored, which sibling plugin's version to keep on a rollback (`v in installs(...)`), and the release flow.
Limit: `set_json_version` is a text edit, not a JSON parser; `entry_offset` finds the first `"name": "<name>"` anywhere, so an owner or author block with the same name misleads it.
