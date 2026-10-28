from __future__ import annotations

from types import MappingProxyType

import child_env
from child_env import scrub


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
