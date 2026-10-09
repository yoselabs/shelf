# launchd-agent

**Stop caring how a program starts at login on macOS.** Render a per-user LaunchAgent plist,
load it into the user's launchd, unload it, and ask whether it is installed and loaded.

```python
import launchd_agent as la

path = la.install(
    label="dev.example.menubar",
    argv=[sys.executable, "-m", "example.menubar"],
    env={"PATH": la.launch_path(["git", "claude"])},   # launchd hides Homebrew and ~/.local/bin
    log_path=state_dir / "login-item.log",
    agents_dir=la.user_agents_dir(),
    working_dir=project,
)                                       # raises la.LaunchdError if launchd refuses
la.status("dev.example.menubar", agents_dir=la.user_agents_dir())   # LoginItemStatus(installed, loaded)
la.uninstall("dev.example.menubar", agents_dir=la.user_agents_dir())
```

The plist has `RunAtLoad` and `KeepAlive`: launchd starts the program at login and restarts
it when it dies. Every launchctl call goes through `run_launchctl`, which a test replaces with
a fake.

## Sharp edges

- **A refused `launchctl bootstrap` is a failure.** It happens when the label is already
  loaded or the domain rejects it. `install` removes the plist it wrote and raises
  `LaunchdError`; a plist left on disk with nothing loaded reads as installed forever.
- **launchd's PATH is `/usr/bin:/bin:/usr/sbin:/sbin`.** A program that shells out to a tool
  from Homebrew or `~/.local/bin` finds nothing at login. `launch_path(tools)` puts each
  tool's folder in front.
- The log's folder is created by `install`; launchd does not create it.
- macOS only at run time; the module imports anywhere. Stdlib only.
