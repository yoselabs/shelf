"""Fitness of the profile set: every stack the shelf supports can say how its layering is enforced (design D4)."""

from __future__ import annotations

import pytest
from blueprint.concerns.stacks.profile_data import load_profiles
from blueprint.concerns.stacks.stack import ROLES

_PROFILES = load_profiles()


def _of(family: str) -> list[str]:
    return sorted(s for s, p in _PROFILES.items() if p.family == family)


def test_every_profile_declares_its_family() -> None:
    assert [s for s, p in _PROFILES.items() if p.family not in {"language", "artifact"}] == []


@pytest.mark.parametrize("stack", _of("language"))
def test_every_language_profile_has_an_architecture_role_that_is_not_na(stack: str) -> None:
    role = _PROFILES[stack].roles.get("architecture")
    assert role is not None, f"{stack} has no architecture role"
    assert not role.na, f"{stack}: architecture is na ({role.na}); a language stack with no layering tool is not supported"
    assert not role.untested, f"{stack}: architecture is untested"
    assert role.tool, f"{stack}: architecture names no tool"


@pytest.mark.parametrize("stack", _of("artifact"))
def test_an_artifact_profile_says_why_it_has_no_layers_or_names_its_policy_tool(stack: str) -> None:
    role = _PROFILES[stack].roles.get("architecture")
    assert role is not None
    assert role.na.strip() or role.tool, f"{stack}: architecture needs a written `na` reason or a tool"


@pytest.mark.parametrize("stack", ["node", "node-tooling"])
def test_the_researched_stacks_answer_every_role(stack: str) -> None:
    assert set(_PROFILES[stack].roles) >= set(ROLES)


def test_no_profile_row_mentions_a_makefile() -> None:
    # shelf-rofp: the runner is just (ADR 0023) and a Makefile is not read (ADR 0028): no profile looks for one.
    from blueprint.concerns.stacks.profile_data import PROFILE_DIR  # noqa: PLC0415 -- only this test reads the folder

    assert [p.name for p in PROFILE_DIR.rglob("*.toml") if "Makefile" in p.read_text()] == []


def test_node_tooling_extends_node_and_overrides_only_what_differs() -> None:
    from blueprint.concerns.stacks.profile_data import PROFILE_DIR  # noqa: PLC0415 -- only this test reads the folder

    node, tooling = _PROFILES["node"], _PROFILES["node-tooling"]
    assert set(tooling.roles) == set(node.roles)
    assert {r for r in tooling.roles if tooling.roles[r] != node.roles[r]} == {"types", "tests", "coverage"}
    assert "extends" in (PROFILE_DIR / "node-tooling.toml").read_text()
    assert (PROFILE_DIR / "node-tooling.toml").read_text().count("[[role]]") == 3
