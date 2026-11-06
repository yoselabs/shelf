"""The task as a specification, and what is wrong with one."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Trust(StrEnum):
    """Who vouches for a task: the owner wrote or raised it (``owned``), or an agent filed it (``proposed``)."""

    PROPOSED = "proposed"
    OWNED = "owned"


class Remedy(StrEnum):
    """Who can fix a finding: the owner decides, a mechanical rewrite, or an agent investigates."""

    OWNER = "owner"
    MECHANICAL = "mechanical"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class Task:
    """One unit of work as the owner would sign it. ``acceptance`` entries are a command plus its expected result."""

    id: str
    title: str
    why: str = ""
    touches: tuple[str, ...] = ()
    acceptance: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    trust: Trust = Trust.PROPOSED
    status: str = "open"


@dataclass(frozen=True, slots=True)
class Finding:
    """One rule a task breaks, with who can fix it."""

    task: str
    repo: str
    rule: str
    remedy: Remedy
    why: str
