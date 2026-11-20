# app-dirs — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.3.0: breaking: `config_dir/state_dir/cache_dir/data_dir(app, *, env, home)` lose `plugin_data` and `create` (pure XDG lookups); new `plugin_dir(kind, app, *, env, home)` (`$CLAUDE_PLUGIN_DATA/<kind>` when set and absolute, else the XDG folder; kind is `Kind = Literal['config','state','cache','data']`) and `ensure(path) -> Path` (mkdir -p); no in-tree caller used the removed keywords
- 0.2.0: new `data_dir(app, *, plugin_data, create, env, home)` (`$XDG_DATA_HOME/<app>` else `~/.local/share/<app>`); new `tool_home(tool, env_var=None, *, env, home) -> Path` (`$<env_var>` if set and non-empty else `~/.<tool>`; relative value kept as given)
