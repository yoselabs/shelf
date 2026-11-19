# app-dirs — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.2.0: new `data_dir(app, *, plugin_data, create, env, home)` (`$XDG_DATA_HOME/<app>` else `~/.local/share/<app>`); new `tool_home(tool, env_var=None, *, env, home) -> Path` (`$<env_var>` if set and non-empty else `~/.<tool>`; relative value kept as given)
