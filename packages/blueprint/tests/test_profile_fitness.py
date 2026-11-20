"""Fitness of the profile set: every stack the shelf supports can say how its layering is enforced (design D4)."""

from __future__ import annotations

import pytest
from blueprint.concerns.stack import ROLES, load_profiles

_PROFILES = load_profiles()


# Stacks that carry no layered code: their architecture role is `na`, and the reason must be written (owner to confirm, shelf-jc7r.4).
_NOT_LAYERED = {"dockerfile": "image build files", "nix": "host configuration", "shell": "leaf scripts"}


@pytest.mark.parametrize("stack", sorted(_NOT_LAYERED))
def test_a_stack_without_layered_code_says_why_its_architecture_is_na(stack: str) -> None:
    role = _PROFILES[stack].roles.get("architecture")
    assert role is not None
    assert role.na.strip(), f"{stack}: architecture needs a tool or a written `na` reason"


@pytest.mark.parametrize("stack", sorted(set(_PROFILES) - set(_NOT_LAYERED)))
def test_every_layered_stack_has_an_architecture_role_that_is_not_na(stack: str) -> None:
    role = _PROFILES[stack].roles.get("architecture")
    assert role is not None, f"{stack} has no architecture role"
    assert not role.na, f"{stack}: architecture is na ({role.na}); a stack with no layering tool is not supported"
    assert not role.untested, f"{stack}: architecture is untested"
    assert role.tool, f"{stack}: architecture names no tool"


@pytest.mark.parametrize("stack", ["node", "go", "rust"])
def test_the_researched_stacks_answer_every_role(stack: str) -> None:
    assert set(_PROFILES[stack].roles) >= set(ROLES)
