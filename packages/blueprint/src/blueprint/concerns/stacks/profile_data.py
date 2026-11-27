"""The data model of a stack or framework profile (`profiles/*.toml`) and its loader."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROFILE_DIR = Path(__file__).resolve().parent.parent.parent / "profiles"


@dataclass(frozen=True)
class Role:
    """One role in a profile: the tool, how to install it, what proves it is set up and that it runs."""

    role: str
    tool: str = ""
    install: str = ""
    config: tuple[dict[str, Any], ...] = ()  # Any: parsed TOML rows, keys read by the checks
    gate: str = ""
    # Other ways to prove the role runs: each is a `label`, a `gate` regex over the gate text, and
    # optionally a `path`/`contains` the repo's config must also hold.
    alternatives: tuple[dict[str, Any], ...] = ()  # Any: parsed TOML rows
    untested: str = ""
    na: str = ""
    # An outcome contract (instead of `gate`): the role is judged by what the gate does, whatever tool does it.
    # `runs`: some step the gate reaches runs a test runner (any regex matches). `floor`: some step enforces a floor,
    # where each `floors` entry is a `label`, a `gate` regex over the gate text and optionally a `path`/`contains` the repo must hold.
    outcome: str = ""
    runs: tuple[str, ...] = ()
    floors: tuple[dict[str, Any], ...] = ()  # Any: parsed TOML rows
    # Where the role's executable may live, besides PATH: `$PATH`, `$DOTNET_ROOT` or an absolute folder. A
    # toolchain role names them when a second install can be the one a tool resolves (Godot's dotnet).
    installs: tuple[str, ...] = ()
    # A purpose (ADR 0026): the row applies only to a repo with this fact, `shipped-image` or `deployed`, else it is not applicable.
    requires: str = ""
    # Optional: a repo that has not set the role up is not judged (not applicable); one that has must still run it (failing otherwise).
    optional: bool = False


@dataclass(frozen=True)
class StackProfile:
    """A stack's answers, one per role."""

    stack: str
    status: str
    source: str
    roles: dict[str, Role] = field(default_factory=dict)
    # `language` (code that grows layers: needs a layering tool) or `artifact` (a file format: architecture is `na` with its reason).
    family: str = ""
    # Tools the stack runs, each with the file that says so (`uv = "uv.lock"`): blueprint.tool_pins wants them pinned in mise.toml.
    pins: dict[str, str] = field(default_factory=dict)
    # The command that writes the stack's gate (the fix of gate.one-command when there is no justfile); empty: an agent writes it.
    onboard: str = ""
    # How the stack pins `just` and how it is then run (`uv add --dev rust-just`, `run it as uv run just check`); empty: mise.toml.
    runner_pin: str = ""
    runner_run: str = ""


# A detected stack with no profile of its own that reads as another's: a Python repo without a lockfile is read as python-uv.
ALIASES = {"python": "python-uv"}


def profile_for(stack: str, profiles: dict[str, StackProfile]) -> StackProfile | None:
    """The profile that answers for a detected stack."""
    return profiles.get(stack) or profiles.get(ALIASES.get(stack, ""))


def load_profiles(directory: Path = PROFILE_DIR) -> dict[str, StackProfile]:
    """Every `<stack>.toml` in `directory`."""
    profiles: dict[str, StackProfile] = {}
    for path in sorted(directory.glob("*.toml")):  # frameworks/ is a subfolder, not read here
        data: dict[str, Any] = tomllib.loads(path.read_text())
        roles = {
            r["role"]: Role(
                role=r["role"],
                tool=r.get("tool", ""),
                install=r.get("install", ""),
                config=tuple(r.get("config", ())),
                gate=r.get("gate", ""),
                alternatives=tuple(r.get("alternative", ())),
                untested=r.get("untested", ""),
                na=r.get("na", ""),
                outcome=r.get("outcome", ""),
                runs=tuple(r.get("runs", ())),
                floors=tuple(r.get("floor", ())),
                installs=tuple(r.get("installs", ())),
                requires=r.get("requires", ""),
                optional=bool(r.get("optional", False)),
            )
            for r in data.get("role", [])
        }
        profiles[data["stack"]] = StackProfile(
            data["stack"],
            data.get("status", "provisional"),
            data.get("source", ""),
            roles,
            data.get("family", ""),
            dict(data.get("pins", {})),
            data.get("onboard", ""),
            data.get("runner_pin", ""),
            data.get("runner_run", ""),
        )
    return profiles
