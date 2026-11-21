"""Beads in the git hooks: `bd sync` at pre-push (fatal) and on post-merge and post-checkout.

Owned by the beads plugin, which requires git-hooks; the hooks plugin knows nothing of bd (mission blueprint-plugins, step 5).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from blueprint.concerns.gate_hooks import HOOK_CONFIG
from blueprint.concerns.hooks import hooks_in
from blueprint.model import check, failing, not_applicable, passing, uses_beads

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_NONE = f"no {HOOK_CONFIG}: nothing to judge (gate.hooks-recipe asks for one)"
_SYNC = re.compile(r"\bbd\s+sync\b")
_SYNC_FIX = (
    "add the recipe's `bd-sync-push` (pre-push) and `bd-sync-pull` (post-merge, post-checkout) hooks: `bd sync` pulls, checks conflicts, "
    "pushes with retry and exits 2 (conflict), 3 (race), 4 (stuck); bare `bd dolt push` is a fallback, not the routine step"
)


@check(
    "hooks.beads-sync",
    "a beads repo syncs through `bd sync`: at pre-push (fatal) and on post-merge and post-checkout (pull)",
    applies=uses_beads,
)
def beads_sync(ctx: Context) -> Finding:
    """Bead data travels on refs/dolt/data, which git never moves; without these hooks a clone drifts and a push can race silently."""
    config = ctx.read(HOOK_CONFIG)
    if config is None:
        return not_applicable(_NONE)
    synced = {stage for h in hooks_in(config) if _SYNC.search(h.entry) for stage in h.stages}
    missing = [stage for stage in ("pre-push", "post-merge", "post-checkout") if stage not in synced]
    if missing:
        return failing(f"no `bd sync` hook at: {', '.join(missing)}", _SYNC_FIX)
    return passing("`bd sync` runs at pre-push, post-merge and post-checkout")
