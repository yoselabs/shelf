from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

import child_env
from child_env import VENV_NAMES, scrub, scrub_current, without_venv

if TYPE_CHECKING:
    import pytest


def test_accepts_any_mapping_and_returns_a_plain_dict() -> None:
    out = scrub(MappingProxyType({"PATH": "/bin", "CLAUDECODE": "1"}))
    assert out == {"PATH": "/bin"}
    assert type(out) is dict


def test_empty_env_gives_empty_dict() -> None:
    assert scrub({}) == {}


def test_default_tuples_are_exported() -> None:
    for name in ("APP_PREFIXES", "APP_NAMES", "CREDENTIAL_PREFIXES", "CREDENTIAL_NAMES", "CREDENTIAL_MARKERS"):
        assert isinstance(getattr(child_env, name), tuple)
        assert name in child_env.__all__
    assert {"CLAUDE_", "ANTHROPIC_", "DELEGATE_", "MCP_", "OTEL_"} <= set(child_env.APP_PREFIXES)


def test_a_keep_generator_is_consumed_once() -> None:
    out = scrub({"CLAUDE_A": "1", "CLAUDE_B": "2"}, keep=(n for n in ("CLAUDE_A", "CLAUDE_B")))
    assert out == {"CLAUDE_A": "1", "CLAUDE_B": "2"}


VENV = "/work/.venv"
VENV_ENV = {
    "VIRTUAL_ENV": VENV,
    "VIRTUAL_ENV_PROMPT": "(work)",
    "PYTHONHOME": "/py",
    "__PYVENV_LAUNCHER__": "/py/bin/python",
    "PYTHONEXECUTABLE": "/py/bin/python",
    "PATH": f"{VENV}/bin:/usr/bin:/bin",
    "HOME": "/home/u",
    "PYTHONPATH": "/lib",
    "UV_CACHE_DIR": "/c",
}


def test_without_venv_removes_the_venv_variables_and_its_bin_from_path() -> None:
    assert without_venv(VENV_ENV) == {"PATH": "/usr/bin:/bin", "HOME": "/home/u", "PYTHONPATH": "/lib", "UV_CACHE_DIR": "/c"}
    assert set(VENV_NAMES) == {"VIRTUAL_ENV", "VIRTUAL_ENV_PROMPT", "PYTHONHOME", "__PYVENV_LAUNCHER__", "PYTHONEXECUTABLE"}


def test_without_venv_removes_only_the_exact_bin_entry_and_keeps_order() -> None:
    env = {"VIRTUAL_ENV": VENV, "PATH": f"/a:{VENV}/bin:{VENV}/bin2:{VENV}:/other/.venv/bin:{VENV}/bin/:/b"}
    assert without_venv(env)["PATH"] == f"/a:{VENV}/bin2:{VENV}:/other/.venv/bin:{VENV}/bin/:/b"


def test_without_venv_leaves_path_alone_when_no_virtual_env_is_set() -> None:
    env = {"PYTHONHOME": "/py", "PATH": f"{VENV}/bin:/usr/bin"}
    assert without_venv(env) == {"PATH": f"{VENV}/bin:/usr/bin"}


def test_without_venv_works_without_path_and_never_mutates_the_input() -> None:
    env = {"VIRTUAL_ENV": VENV, "X": "1"}
    snapshot = dict(env)
    assert without_venv(env) == {"X": "1"}
    assert env == snapshot


def test_scrub_leaves_the_venv_alone_by_default() -> None:
    assert scrub(VENV_ENV) == VENV_ENV


def test_scrub_strip_venv_strips_it_next_to_the_other_rules() -> None:
    env = {**VENV_ENV, "CLAUDECODE": "1", "GH_TOKEN": "t"}
    assert scrub(env, strip_venv=True) == without_venv(VENV_ENV)


def test_strip_venv_wins_over_keep_and_still_cleans_path_when_drop_removed_virtual_env() -> None:
    kept = scrub(VENV_ENV, keep=["VIRTUAL_ENV", "PYTHON*"], strip_venv=True)
    assert "VIRTUAL_ENV" not in kept
    assert "PYTHONHOME" not in kept
    assert kept["PYTHONPATH"] == "/lib"
    dropped = scrub(VENV_ENV, drop=["VIRTUAL_ENV"], strip_venv=True)
    assert dropped["PATH"] == "/usr/bin:/bin"


def test_scrub_current_strips_the_venv_of_the_process(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in VENV_ENV.items():
        monkeypatch.setenv(name, value)
    out = scrub_current(strip_venv=True)
    assert not set(VENV_NAMES) & set(out)
    assert f"{VENV}/bin" not in out["PATH"].split(":")
