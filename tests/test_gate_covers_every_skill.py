"""Every `skills/<name>/` directory must carry eval coverage, or it is invisible to the gate.

Mirrors `test_gate_covers_every_package.py`'s shape for the `skill` Kind
(skill-as-shelf-kind, resolution 0014): a skill member with a `SKILL.md` but no
`evals/` directory can be committed and never checked by anything —
`claude plugin eval` only runs against cases that exist, so silence here is the
same failure class as a package suite absent from `testpaths`.

No non-zero population floor yet, unlike the package gate's `_MIN_PACKAGES_WITH_TESTS`:
the `skill` Kind has zero members as of this change (skill-as-shelf-kind only builds the
contract; authoring a skill is a separate, later change). Add a floor once a real skill
exists, matching the package gate's own anti-vacuity reasoning.
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


def test_every_skill_has_eval_coverage() -> None:
    """A skill with no `evals/` directory is committed but never checked by `claude plugin eval`."""
    uncovered = [p.name for p in _skill_dirs() if not (p / "evals").is_dir()]
    assert not uncovered, (
        f"skill(s) with a SKILL.md but no evals/ directory, so `claude plugin eval` never checks "
        f"them: {uncovered}. Add skills/<name>/evals/ before marking the catalog entry active."
    )
