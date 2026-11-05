# Runbook — task-loop profile

Slots: 2 slots under `.slots`, base `origin/main`, setup `uv sync --locked`.
Engine: `land_mode: pr`, `pick_label: auto`.
Checks: only check `uv run just check`.
Landing: Open the PR without merging it. The lead session merges the PR.
