"""A per-user LaunchAgent, against a temporary LaunchAgents folder and a fake ``launchctl``.

Moved from a2kay (owner/login_item.py), where the agent keeps its menu-bar supervisor
alive across login and reboot. The real ``~/Library/LaunchAgents`` and the user's launchd
are never touched.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

import launchd_agent as la
import pytest
from launchd_agent.testing import FakeLaunchctl, RefusingLaunchctl

_LABEL = "dev.example.agent"


def _install(tmp_path: Path, ctl: la.Launchctl) -> Path:
    return la.install(
        label=_LABEL,
        argv=["/tools/bin/python", "-m", "example.app"],
        env={"EXAMPLE_HOME": "/home"},
        log_path=tmp_path / "logs" / "agent.log",
        agents_dir=tmp_path / "LaunchAgents",
        working_dir=tmp_path / "work",
        run_launchctl=ctl,
    )


def test_render_plist_declares_run_at_load_keepalive_and_the_env(tmp_path: Path) -> None:
    doc = la.render_plist(
        label=_LABEL,
        argv=["/tools/bin/python", "-m", "example.app"],
        working_dir=Path("/vault"),
        env={"EXAMPLE_HOME": "/vault"},
        log_path=tmp_path / "agent.log",
    )
    parsed = plistlib.loads(doc.encode())
    assert parsed["Label"] == _LABEL
    assert parsed["RunAtLoad"] is True
    assert parsed["KeepAlive"] is True
    assert parsed["ProgramArguments"] == ["/tools/bin/python", "-m", "example.app"]
    assert parsed["EnvironmentVariables"]["EXAMPLE_HOME"] == "/vault"
    assert parsed["WorkingDirectory"] == "/vault"
    assert parsed["StandardOutPath"].endswith("agent.log")
    assert parsed["StandardErrorPath"] == parsed["StandardOutPath"]
    assert parsed["ProcessType"] == "Interactive"


def test_render_plist_without_a_working_dir_names_none(tmp_path: Path) -> None:
    doc = la.render_plist(label=_LABEL, argv=["/bin/true"], env={}, log_path=tmp_path / "a.log", keep_alive=False)
    parsed = plistlib.loads(doc.encode())
    assert "WorkingDirectory" not in parsed
    assert parsed["KeepAlive"] is False


def _tools(root: Path, **folders: tuple[str, ...]) -> dict[str, str]:
    """An env whose PATH holds a folder per name in ``folders`` (each with the listed executables); returns that env."""
    dirs = []
    for folder, names in folders.items():
        where = root / folder
        where.mkdir(parents=True, exist_ok=True)
        for name in names:
            exe = where / name
            exe.write_text("#!/bin/sh\n")
            exe.chmod(0o755)
        dirs.append(str(where))
    return {"PATH": ":".join(dirs)}


def test_path_puts_a_tools_folder_before_launchds_default(tmp_path: Path) -> None:
    env = _tools(tmp_path, brew=("git-lfs",))
    assert la.launch_path(["git-lfs"], env) == f"{tmp_path / 'brew'}:/usr/bin:/bin:/usr/sbin:/sbin"


def test_path_is_launchds_default_when_nothing_is_found(tmp_path: Path) -> None:
    assert la.launch_path(["git", "git-lfs"], _tools(tmp_path, brew=())) == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert la.launch_path(["git"], {}) == "/usr/bin:/bin:/usr/sbin:/sbin"


def test_a_tool_already_in_a_launchd_folder_adds_nothing() -> None:
    assert la.launch_path(["sh"], {"PATH": "/bin"}) == "/usr/bin:/bin:/usr/sbin:/sbin"


def test_path_names_each_folder_once(tmp_path: Path) -> None:
    env = _tools(tmp_path, brew=("git", "git-lfs"))
    assert la.launch_path(["git", "git-lfs"], env) == f"{tmp_path / 'brew'}:/usr/bin:/bin:/usr/sbin:/sbin"


def test_path_keeps_the_tools_order(tmp_path: Path) -> None:
    env = _tools(tmp_path, brew=("git-lfs",), local=("claude",))
    expected = f"{tmp_path / 'local'}:{tmp_path / 'brew'}:/usr/bin:/bin:/usr/sbin:/sbin"
    assert la.launch_path(["claude", "git-lfs"], env) == expected


def test_path_does_not_look_in_the_process_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ambient = _tools(tmp_path, ambient=("only-in-ambient",))
    monkeypatch.setenv("PATH", ambient["PATH"])
    assert la.launch_path(["only-in-ambient"], {"PATH": ""}) == "/usr/bin:/bin:/usr/sbin:/sbin"


def test_install_status_uninstall_round_trip(tmp_path: Path) -> None:
    agents = tmp_path / "LaunchAgents"
    ctl = FakeLaunchctl()
    plist = _install(tmp_path, ctl)
    assert plist.exists() and plist == agents / f"{_LABEL}.plist"
    assert (tmp_path / "logs").is_dir()  # launchd will not create the log's folder
    assert any(c[1] == "bootstrap" for c in ctl.calls)  # it was loaded, not just written

    st = la.status(_LABEL, agents_dir=agents, run_launchctl=ctl)
    assert st.installed is True and st.loaded is True
    assert st.plist_path == plist

    assert la.uninstall(_LABEL, agents_dir=agents, run_launchctl=ctl) is True
    assert not plist.exists()
    st2 = la.status(_LABEL, agents_dir=agents, run_launchctl=ctl)
    assert st2.installed is False and st2.loaded is False


def test_install_reports_a_refused_bootstrap(tmp_path: Path) -> None:
    """A non-zero `launchctl bootstrap` is a failed install, not a successful one.

    Discarding the exit code told the user the agent was set up when launchd had refused
    it and nothing would start at boot (a2kay-2bf).
    """
    with pytest.raises(la.LaunchdError) as excinfo:
        _install(tmp_path, RefusingLaunchctl())
    assert "5" in str(excinfo.value)
    # The plist is cleaned up: a file on disk with nothing loaded reads as installed.
    assert not (tmp_path / "LaunchAgents" / f"{_LABEL}.plist").exists()


def test_uninstall_absent_is_a_clean_noop(tmp_path: Path) -> None:
    ctl = FakeLaunchctl()
    assert la.uninstall(_LABEL, agents_dir=tmp_path / "LaunchAgents", run_launchctl=ctl) is False
    assert ctl.calls == []


def test_the_commands_address_the_users_gui_domain(tmp_path: Path) -> None:
    ctl = FakeLaunchctl()
    _install(tmp_path, ctl)
    la.status(_LABEL, agents_dir=tmp_path / "LaunchAgents", run_launchctl=ctl)
    assert la.domain().startswith("gui/")
    assert ctl.calls[0][:3] == ["launchctl", "bootstrap", la.domain()]
    assert ctl.calls[1] == ["launchctl", "print", f"{la.domain()}/{_LABEL}"]


def test_the_real_runner_captures_and_never_raises() -> None:
    result = la.run_launchctl(["sh", "-c", "echo out; exit 3"])
    assert result.returncode == 3
    assert result.stdout == "out\n"


def test_user_agents_dir_is_under_the_given_home(tmp_path: Path) -> None:
    assert la.user_agents_dir(tmp_path) == tmp_path / "Library" / "LaunchAgents"


def test_the_real_runner_answers_a_hung_launchctl_with_exit_124_not_a_hang() -> None:
    result = la.run_launchctl(["sh", "-c", "sleep 30"], timeout=0.2)
    assert result.returncode == 124
    assert "no answer" in result.stderr
