"""Culture templates: the docs/agents/ files and the AGENTS.md managed block a repo carries.

`blueprint template` copies what is missing and never overwrites a file the repo already has; the
managed block in AGENTS.md is the one exception, rewritten between its markers on every run.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blueprint.model import Profile

TEMPLATES = Path(__file__).resolve().parent / "templates"
ALWAYS = ("constitution", "working-with-agents", "gate", "testing", "architecture", "domain")
WITH_BEADS = ("issue-tracker",)
PER_STACK = {"python-uv": "python", "python": "python", "dotnet": "dotnet"}
PER_FRAMEWORK = {"godot": "godot"}
BEGIN, END = "<!-- blueprint:begin -->", "<!-- blueprint:end -->"
_STACK_TRIGGER = "before writing or changing {name} code"
PLACEHOLDER = re.compile(r"\{\{[a-z_]+\}\}")


def required(profile: Profile) -> list[str]:
    """The docs/agents/<name>.md files this profile requires, by template name."""
    names = list(ALWAYS) + (list(WITH_BEADS) if profile.tracker == "beads" else [])
    names += [PER_STACK[s] for s in profile.stacks if s in PER_STACK]
    names += [PER_FRAMEWORK[f] for f, _ in profile.frameworks if f in PER_FRAMEWORK]
    return list(dict.fromkeys(names))


def block(profile: Profile) -> str:
    """The AGENTS.md managed block, its stack rows filled from the profile."""
    rows = [
        f"| [docs/agents/{n}.md](docs/agents/{n}.md) | {_STACK_TRIGGER.format(name=n)} |"
        for n in required(profile)
        if n not in ALWAYS and n not in WITH_BEADS
    ]
    return (TEMPLATES / "agents-md-block.md").read_text().replace("{{stack_rows}}", "\n".join(rows)).strip() + "\n"


def install(repo: Path, profile: Profile) -> list[str]:
    """Copy each missing docs/agents file and write the managed block; return what changed."""
    changed: list[str] = []
    for name in required(profile):
        target = repo / "docs" / "agents" / f"{name}.md"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((TEMPLATES / "agents" / f"{name}.md").read_text())
            changed.append(str(target.relative_to(repo)))
    agents = repo / "AGENTS.md"
    text = agents.read_text() if agents.exists() else "# AGENTS.md\n"
    new_block = block(profile)
    if BEGIN in text and END in text:
        updated = text[: text.index(BEGIN)] + new_block.rstrip("\n") + text[text.index(END) + len(END) :]
    else:
        updated = text.rstrip("\n") + "\n\n" + new_block
    if updated != text:
        agents.write_text(updated)
        changed.append("AGENTS.md (managed block)")
    return changed
