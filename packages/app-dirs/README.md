# app-dirs

**Stop copying the XDG lookup.** Where an app keeps its config, state and cache, decided in one place.
POSIX only; macOS uses the same XDG layout as Linux.

```python
from pathlib import Path
from app_dirs import cache_dir, config_dir, plugin_data_dir, state_dir

config_dir("task-loop")                    # $XDG_CONFIG_HOME/task-loop, else ~/.config/task-loop
state_dir("task-loop")                     # $XDG_STATE_HOME/task-loop,  else ~/.local/state/task-loop
cache_dir("task-loop", create=True)        # $XDG_CACHE_HOME/task-loop,  else ~/.cache/task-loop; mkdir -p
config_dir("task-loop", plugin_data=True)  # $CLAUDE_PLUGIN_DATA/config when that is set, else as above
config_dir("x", env={"XDG_CONFIG_HOME": "/cfg"}, home=Path("/h"))  # no os.environ patching in tests
plugin_data_dir()                          # the CLAUDE_PLUGIN_DATA folder, or None
```

- An unset, empty or relative variable is ignored (the XDG spec), for the XDG variables and for
  `CLAUDE_PLUGIN_DATA` alike.
- `plugin_data=True` is opt-in: that variable names whichever plugin launched the process, so a
  tool that must not follow it (delegate keeps its own `DELEGATE_CONFIG_DIR`) never reads it.
  With it, config, state and cache are `config/`, `state/` and `cache/` below that folder.
- Nothing is created unless `create=True`; the folder's permissions are the caller's to set.
- `app` is one folder name: empty, `.`, `..` or one holding `/` raises `ValueError`.

## Boundary

Imports no consumer app (`a2web`, `a2kay`) — enforced by `tests/test_boundary_app_dirs.py`.
