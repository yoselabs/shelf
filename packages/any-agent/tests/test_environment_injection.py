"""The harnesses take the environment they look things up in as an argument (shelf-tyld.5, .6): the program is found on the injected
PATH (a miss raises, the ambient PATH is never read), the foreign tools' folders come from app-dirs, and a stopped worker's log
verdict does not depend on the order the filesystem lists files in."""

import os
import stat
from pathlib import Path

import pytest
from child_env import NotFound

import any_agent.harnesses.claude as c
import any_agent.harnesses.codex as x
import any_agent.harnesses.opencode as o
from any_agent import procs
from any_agent.harnesses.claude import ClaudeHarness
from any_agent.harnesses.codex import CodexHarness
from any_agent.harnesses.opencode import OpenCodeHarness
from any_agent.supervisor import LogWatcher


def _program(folder: Path, name: str) -> Path:
    exe = folder / name
    exe.write_text("#!/bin/sh\necho '{\"loggedIn\": true}'\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def test_a_login_probe_looks_for_the_program_on_the_injected_path_only(tmp_path, monkeypatch):
    _program(tmp_path, "claude")
    _program(tmp_path, "codex")
    monkeypatch.setenv("PATH", str(tmp_path))  # the ambient PATH has them; the injected one does not
    assert ClaudeHarness(env={"PATH": "/nonexistent"}).login_probe(5)[0] is None
    assert CodexHarness(env={"PATH": "/nonexistent"}).login_probe(5)[0] is None
    assert ClaudeHarness(env={"PATH": str(tmp_path)}).login_probe(5)[0] is True


def test_the_codex_rollout_folder_is_the_injected_codex_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "ambient"))
    home = tmp_path / "injected"
    day = home / "sessions" / "2026" / "10" / "21"
    day.mkdir(parents=True)
    (day / "rollout-th-7.jsonl").write_text("{}\n")
    found = CodexHarness(env={"CODEX_HOME": str(home)}).transcript("th-7")
    assert found is not None
    assert found.endswith("rollout-th-7.jsonl")
    assert CodexHarness(env={}).transcript("th-7") is None


def test_opencode_data_folders_follow_the_injected_xdg_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "ambient"))
    data = tmp_path / "data"
    assert OpenCodeHarness(env={"XDG_DATA_HOME": str(data)}).log_dir == data / "opencode" / "log"
    # a relative XDG_DATA_HOME is ignored (the XDG spec, app-dirs): the fallback below the home folder
    assert OpenCodeHarness(env={"XDG_DATA_HOME": "rel"}).log_dir == Path.home() / ".local" / "share" / "opencode" / "log"


def test_opencode_is_found_on_the_path_then_in_its_own_bin_and_a_miss_raises(tmp_path):
    with pytest.raises(NotFound):
        OpenCodeHarness(env={"PATH": ""}).find_exe()
    own = Path.home() / ".opencode" / "bin"
    own.mkdir(parents=True)
    _program(own, "opencode")
    assert OpenCodeHarness(env={"PATH": ""}).find_exe() == str(own / "opencode")
    elsewhere = tmp_path / "bin"
    elsewhere.mkdir()
    _program(elsewhere, "opencode")
    assert OpenCodeHarness(env={"PATH": str(elsewhere)}).find_exe() == str(elsewhere / "opencode")
    (own / "opencode").unlink()
    with pytest.raises(NotFound):
        OpenCodeHarness(env={"PATH": ""}).find_exe()


def test_the_harnesses_read_no_process_environment():
    for mod in (c, x, o):
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "os.environ" not in source, mod.__name__
        assert "shutil.which" not in source, mod.__name__


def test_the_log_watcher_reports_the_first_limit_in_file_name_order(tmp_path, monkeypatch):
    for name in ("b.log", "a.log"):
        (tmp_path / name).write_text("")
    watcher = LogWatcher(tmp_path, lambda line: "limit" in line, lambda line: False)
    (tmp_path / "b.log").write_text("limit from b\n")
    (tmp_path / "a.log").write_text("limit from a\n")
    real = Path.glob
    monkeypatch.setattr(Path, "glob", lambda self, pattern: iter(sorted(real(self, pattern), reverse=True)))  # b before a
    stop = watcher.poll()
    assert stop is not None
    assert stop.msg == "limit from a"


def test_no_stop_grace_variable_is_read():
    assert "environ" not in Path(procs.__file__).read_text(encoding="utf-8")
    assert os.environ.get("ANY_AGENT_STOP_GRACE") is None or procs.GRACE_S == 5
