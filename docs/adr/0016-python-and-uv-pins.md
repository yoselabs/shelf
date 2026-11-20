---
id: 0016
title: Python and uv are pinned once each, and images read the pins
statement: one X.Y in .python-version; requires-python ">=X.Y", uncapped, pin inside; uv floored by required-version; images install the pinned uv.
concerns: [stack, gate]
status: accepted
decided_by: owner
updated: 2026-11-20
distilled_into: blueprint stack.python-uv.python-pin, python-range, uv-version, uv-images
---

# 0016 — Python and uv pins

## Decision

| file | holds | rule |
|---|---|---|
| `.python-version` (root, one per workspace) | the interpreter dev and agents run | one `X.Y` line, no patch: the lock carries reproducibility, a patch pin forces downloads |
| `requires-python` in every pyproject | what installers may use | `">=X.Y"`, no upper cap (a cap blocks installs on new Pythons); the pin sits inside every member's range |
| `[tool.uv] required-version` | uv's floor | a different uv rewrites `uv.lock`'s revision |
| container images | the uv they install | `COPY --from=ghcr.io/astral-sh/uv:<pin>`, the exact uv pinned in `mise.toml` (ADR 0024) |

The pin and the range are two facts, not duplication: uv picks the interpreter from the pin, and
resolves and publishes against the range (tested with uv 0.10.12).

## Rejected

- Pin equal to the range everywhere: needless for an app; a library may claim an older Python.
- Patch-level pins: download churn, no gain over the lock.

## History

- 2026-10-11: decided after a2kay's audit (shelf-0ac); research in
  `docs/research/blueprint-skill/research/python-pin.md`. The shelf's packages moved from `>=3.11`
  to `>=3.12`: no CI ran 3.11, so the claim was untested.
- 2026-11-20: ADR 0027 (no repository has CI): the rows that judged CI are gone (`python-range-tested`, `python-ci`, the setup-uv half of `uv-ci`); the image half lives on as `uv-images`.
