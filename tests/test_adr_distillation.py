"""Every ADR must record where (or whether) it lands in the operational loop.

agent-loop.md WORKFLOW: EVOLVE-THE-LOOP requires a `distilled_into:` frontmatter field on
every ADR: a workflow reference, or `N/A - self-enforcing via <test/tool>`. This test fails
if the field is missing, so an ADR can't ship without the judgment call being made and
recorded (openspec change systematize-agent-loop-as-workflows).
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ADRS = sorted((_ROOT / "docs" / "adr").glob("0*.md"))


def test_every_adr_has_a_distillation_field() -> None:
    assert _ADRS, "no ADRs found; did the glob pattern change?"
    for path in _ADRS:
        head = path.read_text().split("\n---", 2)[0]
        assert re.search(r"^distilled_into:[ \t]*\S", head, re.MULTILINE), f"{path.name} is missing a `distilled_into:` frontmatter field"
