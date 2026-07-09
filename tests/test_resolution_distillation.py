"""Every resolution must record where (or whether) it lands in the operational loop.

agent-loop.md WORKFLOW: EVOLVE-THE-LOOP requires a `Distilled into:` frontmatter line on
every resolution — a workflow reference, or `N/A — self-enforcing via <test/tool>`. This
test fails if that line is missing, so a resolution can't ship without the judgment call
being made and recorded (docs/resolutions/systematize-agent-loop-as-workflows change).
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_RESOLUTIONS = sorted((_ROOT / "docs" / "resolutions").glob("0*.md"))
_FIELD = re.compile(r"^-\s+\*\*Distilled into:\*\*\s+\S", re.MULTILINE)


def test_every_resolution_has_a_distillation_field() -> None:
    assert _RESOLUTIONS, "no resolutions found — did the glob pattern change?"
    for path in _RESOLUTIONS:
        text = path.read_text()
        assert _FIELD.search(text), f"{path.name} is missing a `Distilled into:` line"
