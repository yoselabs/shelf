"""Every `skills/<name>/` must have eval cases in `evals/<name>/`, or it is invisible to the gate.

Mirrors `test_gate_covers_every_package.py`'s shape for the `skill` Kind
(skill-as-shelf-kind, resolution 0014): a skill member with a `SKILL.md` but no
cases under `evals/<name>/` can be committed and never checked by anything —
`claude plugin eval` only runs against cases that exist, so silence here is the
same failure class as a package suite absent from `testpaths`.

A population floor, like the package gate's `_MIN_PACKAGES_WITH_TESTS`: a walk that finds
no skill passes the coverage test vacuously.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SKILLS = _ROOT / "skills"


def _skill_dirs() -> list[Path]:
    """Every `skills/<name>/` directory that carries a `SKILL.md`."""
    if not _SKILLS.is_dir():
        return []
    return sorted(p.parent for p in _SKILLS.glob("*/SKILL.md"))


_MIN_SKILLS = 1  # blueprint, 2026-10-10


def test_the_walk_found_the_skills() -> None:
    """Anti-vacuity: the coverage test below means nothing if the walk finds no skill."""
    assert len(_skill_dirs()) >= _MIN_SKILLS


def test_every_skill_has_eval_coverage() -> None:
    """A skill with no `evals/<name>/` cases is committed but never checked by `claude plugin eval`.

    The cases live at the plugin root, not in the skill: `claude plugin eval` refuses an eval
    dir inside `skills/` (resolution 0014, amendment).
    """
    uncovered = [p.name for p in _skill_dirs() if not any((_ROOT / "evals" / p.name).glob("*/prompt.md"))]
    assert not uncovered, (
        f"skill(s) with a SKILL.md but no evals/<name>/<case>/prompt.md, so `claude plugin eval` never "
        f"checks them: {uncovered}. Add a case before marking the catalog entry active."
    )
