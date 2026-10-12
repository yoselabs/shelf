"""`blueprint checkpoints`: every checkpoint blueprint can report, with the fact that turns it on.

Two sources: the registered checks (`model.REGISTRY`) and the rows the stack and framework profiles
produce at run time (`stack.<stack>.<role>`, `framework.<name>.<role>`). Nothing is judged here and no
repo is read; "turned on by" says only what the code knows.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from blueprint import concerns
from blueprint.concerns.framework import FRAMEWORK_DIR
from blueprint.concerns.stack import FRAMEWORK_ROLES, PROFILE_DIR, ROLES, Role, StackProfile, load_profiles
from blueprint.model import REGISTRY, Check

if TYPE_CHECKING:
    from collections.abc import Iterable

concerns.load()


@dataclass(frozen=True)
class Listed:
    """One line of the listing."""

    id: str
    statement: str
    turned_on_by: str


def _turned_on_by(check: Check) -> str:
    if check.applies.__name__ == "<lambda>":
        fact = "always"
    else:
        doc = inspect.getdoc(check.applies)
        fact = doc.splitlines()[0].rstrip(".") if doc else check.applies.__name__
    return f"{fact} (audit only: run with --audit)" if check.audit_only else fact


def _verdict_kind(role: Role | None) -> str:
    if role is None:
        return "untested: the profile does not cover this role"
    if role.untested:
        return f"untested: {role.untested}"
    if role.na:
        return f"na: {role.na}"
    return f"tool: {role.tool}"


def _registered() -> Iterable[Listed]:
    for check in REGISTRY:
        statement = check.statement
        if check.id in {"stack.roles", "framework.roles"}:
            statement += " (rows below, one per detected profile and role)"
        yield Listed(check.id, statement, _turned_on_by(check))


def _profile_rows(kind: str, directory: object, roles: tuple[str, ...]) -> Iterable[Listed]:
    profiles: dict[str, StackProfile] = load_profiles(directory)  # type: ignore[arg-type]
    for name, profile in profiles.items():
        fact = f"the {name} {'stack' if kind == 'stack' else 'framework'} is detected"
        yield Listed(f"{kind}.{name}.profile", f"the shelf has a profile for {name}: the tool for every role", fact)
        for role in roles:
            statement = f"{name} {role}: the profile's tool is set up and run by `just check`"
            yield Listed(f"{kind}.{name}.{role}", statement, f"{fact}; {_verdict_kind(profile.roles.get(role))}")


def listing(prefix: str = "") -> list[Listed]:
    """Every checkpoint whose id starts with `prefix`, sorted by id."""
    everything = [
        *_registered(),
        *_profile_rows("stack", PROFILE_DIR, ROLES),
        *_profile_rows("framework", FRAMEWORK_DIR, FRAMEWORK_ROLES),
    ]
    return sorted((c for c in everything if c.id.startswith(prefix)), key=lambda c: c.id)


def as_json(rows: list[Listed]) -> str:
    return json.dumps([asdict(r) for r in rows], indent=2)


def as_table(rows: list[Listed]) -> str:
    header = Listed("ID", "STATEMENT", "TURNED ON BY")
    shown = [header, *rows]
    id_w = max(len(r.id) for r in shown)
    st_w = max(len(r.statement) for r in shown)
    return "\n".join(f"{r.id:<{id_w}}  {r.statement:<{st_w}}  {r.turned_on_by}".rstrip() for r in shown)
