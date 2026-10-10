"""Framework: each framework on top of a stack (a game engine, a web framework) set up to its profile.

Same mechanism as the stack concern: profiles are data, `profiles/frameworks/<name>.toml`, each with
its own roles. Config paths may start with `{root}`, the folder the framework lives in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.concerns.stack import FRAMEWORK_ROLES, PROFILE_DIR, finding_for, gate_text, judge_role, load_profiles
from blueprint.model import Sub, check_each, not_checked, passing

if TYPE_CHECKING:
    from blueprint.model import Context

FRAMEWORK_DIR = PROFILE_DIR / "frameworks"


@check_each(
    "framework.roles", "each framework's tool for each role, from its profile, is set up and run by `make check`", layer="framework"
)
def roles(ctx: Context) -> list[Sub]:
    """Per detected framework: one profile row, then one row per role its profile names."""
    profiles = load_profiles(FRAMEWORK_DIR)
    reached = gate_text(ctx)
    subs: list[Sub] = []
    names = [name for name, _ in ctx.profile.frameworks]
    for name, root in ctx.profile.frameworks:
        # Two projects of one framework (a game and a prototype spike) get one table each, told apart by folder;
        # `[profile.frameworks]` in blueprint.toml names the real one.
        key = f"{name}@{root}" if names.count(name) > 1 else name
        concern, statement = f"framework/{key}", f"the shelf has a profile for {name}: the tool for every role"
        prof = profiles.get(name)
        if prof is None:
            finding = not_checked(
                f"no standard for {name} yet (found in {root}): blueprint has no profile for it",
                f"research the ideal {name} setup and write blueprint/profiles/frameworks/{name}.toml in the shelf",
                blueprint_gap=True,
            )
            subs.append(Sub(concern, f"framework.{key}.profile", statement, finding))
            continue
        tools = " · ".join(f"{r.role}: {r.tool or '(untested)'}" for r in prof.roles.values() if not r.na)
        note = "" if prof.status == "evidenced" else "; provisional: written, not yet proven in a second repo"
        subs.append(Sub(concern, f"framework.{key}.profile", statement, passing(f"{prof.status} profile, in {root}: {tools}{note}")))
        for role in FRAMEWORK_ROLES:
            judged = judge_role(ctx, name, prof, role, reached, root)
            subs.append(
                Sub(concern, f"framework.{key}.{role}", f"{name} {role}: the profile's tool is set up and run", finding_for(judged))
            )
    return subs
