# launchd-agent — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.3.0: `launch_path(tools, which=shutil.which)`  ⇒  `launch_path(tools, env)`: tools are found on `env["PATH"]` with `child_env.find`; the process PATH is never read
- 0.3.0: `user_agents_dir()` (read `Path.home()`)  ⇒  `user_agents_dir(home)`
- 0.3.0: `run_launchctl(cmd)` had no timeout  ⇒  `run_launchctl(cmd, timeout=LAUNCHCTL_TIMEOUT_S)` (30 s); a launchctl that answers nothing returns exit 124 (`EXIT_TIMEOUT`), never raises, never hangs; new exports `LAUNCHCTL_TIMEOUT_S`, `EXIT_TIMEOUT`
- 0.3.0: new dependency `child-env>=0.2,<1`
