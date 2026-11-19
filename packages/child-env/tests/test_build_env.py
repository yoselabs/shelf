from __future__ import annotations

from typing import TYPE_CHECKING

from child_env import DEFAULT_INHERIT, build_env, scrub

if TYPE_CHECKING:
    import pytest


def test_only_allowlisted_keys_are_inherited() -> None:
    env = {"PATH": "/bin", "HOME": "/h", "LC_ALL": "C", "XDG_DATA_HOME": "/x", "RANDOM_APP_VAR": "1", "GIT_DIR": "/g"}
    assert build_env(env) == {"PATH": "/bin", "HOME": "/h", "LC_ALL": "C", "XDG_DATA_HOME": "/x"}


def test_allow_adds_exact_names_and_prefixes() -> None:
    env = {"PATH": "/bin", "GIT_DIR": "/g", "GIT_AUTHOR_NAME": "n", "OTHER": "1"}
    assert build_env(env, allow=["GIT_*"]) == {"PATH": "/bin", "GIT_DIR": "/g", "GIT_AUTHOR_NAME": "n"}
    assert build_env(env, allow=["OTHER"]) == {"PATH": "/bin", "OTHER": "1"}


def test_secrets_never_pass_by_default_even_under_an_allowed_prefix() -> None:
    env = {"PATH": "/bin", "XDG_RUNTIME_TOKEN": "t", "GIT_PASSWORD": "p"}
    assert build_env(env, allow=["GIT_*"]) == {"PATH": "/bin"}


def test_a_secret_passes_only_when_its_exact_name_is_allowed() -> None:
    env = {"PATH": "/bin", "OPENAI_API_KEY": "k", "ANTHROPIC_API_KEY": "a"}
    assert build_env(env, allow=["OPENAI_API_KEY"]) == {"PATH": "/bin", "OPENAI_API_KEY": "k"}


def test_extra_is_set_last_and_wins() -> None:
    assert build_env({"PATH": "/bin", "HOME": "/h"}, extra={"HOME": "/other", "DELEGATE_DEPTH": "1"}) == {
        "PATH": "/bin",
        "HOME": "/other",
        "DELEGATE_DEPTH": "1",
    }


def test_input_is_not_mutated_and_a_plain_dict_comes_back() -> None:
    env = {"PATH": "/bin", "SECRET": "s"}
    out = build_env(env)
    assert env == {"PATH": "/bin", "SECRET": "s"}
    assert type(out) is dict


def test_default_allowlist_holds_no_secret_looking_name() -> None:
    probe = {n.rstrip("*") + "X": "1" for n in DEFAULT_INHERIT}
    assert scrub(probe) == probe


def test_it_never_reads_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/ambient")
    assert build_env({}) == {}
