"""The blueprint skill's own contract: an owner row is decided per row, never by a blanket yes.

shelf-fkx: provisional recipes applied on a blanket yes broke lifesim clones (shelf-o5a) and
packages (shelf-ir7), so the skill's remediate step must ask for each owner row's own decision.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = Path(__file__).resolve().parents[1] / "skills" / "blueprint" / "SKILL.md"


def _section(text: str, heading: str) -> str:
    start = text.index(f"## {heading}")
    return text[start : text.index("\n## ", start)]


def test_the_remediate_step_asks_per_owner_row_and_rejects_a_blanket_yes_for_them() -> None:
    step = _section(_SKILL.read_text(), "3. Remediate")
    intro = next(line for line in step.splitlines() if "one yes" in line)
    rest = step[step.index("- `owner` rows:") :]
    owner = rest[: rest.index("\n- ") if "\n- " in rest else len(rest)]
    # the blanket yes names what it covers, and the owner's rows are outside it
    assert "one yes covers the `auto` and `agent` rows" in intro
    assert "never the `owner` rows" in intro
    # each owner row is its own decision; grouped reading never merges the decisions
    assert "one decision per row" in owner
    assert "blanket yes never applies an owner row" in owner
    assert "unproven-standard" in owner
