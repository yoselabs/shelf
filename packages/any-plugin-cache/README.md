# any-plugin-cache

What Claude Code has installed of a plugin, which of those a pin may name, where a rollback lands, and a version bump for
`plugin.json` / `marketplace.json` that leaves every other byte alone. Stdlib only; imports no host. The claude dir is a
parameter, so tests (and callers) never need the real `~/.claude`.

```python
from pathlib import Path
from any_plugin_cache import installs, installed_version, pin_ok, previous, set_json_version, entry_offset

claude = Path.home() / ".claude"
found = installs(claude, "iorlas-task-loop", "skills/task-loop/tl.py")   # {"0.23.328": Path(...), ...}
cur = installed_version(claude, "iorlas-task-loop")                      # "" when unrecorded
pin_ok(found, "0.23.300")                                                 # a pin must name an installed dir
previous(found, cur)                                                      # rollback target, "" when none

text = set_json_version(text, "0.24.0", after=entry_offset(text, "iorlas-task-loop") or 0)
```

| function | answers |
|---|---|
| `installs` | `{version: dir}` under `plugins/cache/*/<plugin>/`; dirs lacking `marker` and non-version names are skipped |
| `installed_version` | the user-scope version in `installed_plugins.json`, `""` on any miss |
| `pin_ok` | is `version` installed |
| `previous` | newest install strictly below `current` |
| `behind` | how many installs are newer than `version` |
| `version_key` | dotted ints as an orderable tuple, `None` for anything else |
| `set_json_version` / `entry_offset` | regex edit of one `"version"`; raises `NoVersion` when absent |

Not here: where the pin is stored, and the release flow. Those stay with the caller.
