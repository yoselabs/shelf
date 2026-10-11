---
id: 0016
title: Python and uv are pinned once each, and CI reads the pins
statement: one X.Y in .python-version; requires-python ">=X.Y", uncapped, pin inside; lower bounds below the pin run in CI; uv floored by required-version; CI reads the pin.
concerns: [stack, gate]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: blueprint stack.python-uv.python-pin, python-range, python-range-tested, python-ci, uv-version
---

# 0016 — Python and uv pins

## Decision

| file | holds | rule |
|---|---|---|
| `.python-version` (root, one per workspace) | the interpreter dev, CI and agents run | one `X.Y` line, no patch: the lock carries reproducibility, a patch pin forces downloads |
| `requires-python` in every pyproject | what installers may use | `">=X.Y"`, no upper cap (a cap blocks installs on new Pythons); the pin sits inside every member's range |
| CI | proof of the range | a lower bound below the pin has a CI run on it (`uv run --python X.Y …`); otherwise raise the bound to the pin |
| `[tool.uv] required-version` | uv's floor | a different uv rewrites `uv.lock`'s revision; setup-uv reads the floor |
| CI workflow | where CI gets Python | from `.python-version` through uv; no `actions/setup-python` with a literal version |

The pin and the range are two facts, not duplication: uv picks the interpreter from the pin, and
resolves and publishes against the range (tested with uv 0.10.12).

## Rejected

- Pin equal to the range everywhere: needless for an app; libraries may claim older Pythons if CI runs them.
- Patch-level pins: download churn, no gain over the lock.
- `actions/setup-python`: a second source for the version that drifts from the pin.

## History

- 2026-10-11: decided after a2kay's audit (shelf-0ac); research in
  `openspec/changes/blueprint-skill/research/python-pin.md`. The shelf's packages moved from `>=3.11`
  to `>=3.12`: no CI ran 3.11, so the claim was untested.
