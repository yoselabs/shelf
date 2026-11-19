# mcp-clients — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.2.0: `client_statuses(server, home, *, which=shutil.which, ...)`  ⇒  `client_statuses(server, home, *, env, ...)` (`env` required): a client's program is found with `child_env.find` on `env["PATH"]`; the process PATH is never read; `install_dir` under `home` is still checked by existence
- 0.2.0: new dependency `child-env>=0.2,<1`
