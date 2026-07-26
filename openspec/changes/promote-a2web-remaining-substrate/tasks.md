# Tasks

Per-package cycle = PROMOTE workflow (agent-loop.md): extract behind a Capability
→ boundary test → foreign-soil install gate (D6) → `make check` in worktree → tag
+ push → repoint a2web (tracked in a2web `shelf-sweep-promotions`) → close loop
(catalog + ledger). No tag is cut until D6 passes.

## 0. Setup & governance
- [x] 0.1 Worktree `../shelf-a2web` on `work/a2web`, reset to `main` (2026-07-26).
- [x] 0.2 Resolution 0013 (promote to be challenged) + agent-loop distillation — committed `35a178b`.
- [x] 0.3 a2web dead-leftover cleanup (`content_extract`/`cookie_store`/`html_fragment`/`record_extract` — pycache-only, source already `git rm`'d in a prior repoint).

## 1. plugin-surface  (IN PROGRESS)
- [x] 1.1 Extract `_plugin.py` → `packages/plugin-surface/src/plugin_surface/`; drop `settings_prefix`; inject logger (D1).
- [x] 1.2 README + pyproject (zero deps, stdlib only).
- [x] 1.3 Port acceptance suite (`tests/` + `_fixture_surface/`, consumer-free `object()` context; cover logger injection, priority sort, wrong-type branch).
- [x] 1.4 Boundary test (`test_boundary_plugin_surface.py`).
- [x] 1.5 Foreign-soil install gate (D6) PASS (clean venv, built artifact, 9/9). `make check` green in worktree (339 passed, 88.47%).
- [x] 1.6 Tagged `plugin-surface-v0.1.0`; pushed.
- [x] 1.7 Repointed a2web (imports → `plugin_surface`; `logger=get_logger()` at 6 sites; committed a2web `9ce0711`, gate green 1243/90.26%).

## 2. llm-wobble
- [ ] 2.1 Extract `packages/llm_extract/wobble/`; parameterize the `getLogger("a2kit")` (D2). Do NOT carry any back-compat shim.
- [ ] 2.2 Leave `_policies.py` tables in a2web (product).
- [ ] 2.3 Port `tests/packages/llm_extract/test_wobble.py`; boundary test; D6 gate.
- [ ] 2.4 `make check` green; tag `llm-wobble-v0.1.0`; push; repoint a2web.

## 3. anyllm.cost  (EVOLVE)
- [ ] 3.1 Add `anyllm.cost` (`CostPolicy`, `assert_within_budget`, `with_cost_guard`, `CostViolation`), keyed on `anyllm.ProviderName` (D4).
- [ ] 3.2 Monotonicity check (resolution 0007): exposes more, removes nothing.
- [ ] 3.3 Port `tests/packages/test_llm_cost_guard.py`; D6 gate.
- [ ] 3.4 `make check`; tag `anyllm-vX.Y.0` (minor bump, additive); push; repoint a2web.

## 4. llm-cache
- [ ] 4.1 Extract `packages/llm_extract/cache.py` on `sqlite-resource` + `anyllm`; return `anyllm.Completion` (D3).
- [ ] 4.2 Boundary test; acceptance suite; D6 gate.
- [ ] 4.3 `make check`; tag `llm-cache-v0.1.0`; push; repoint a2web.

## 5. any-browser  (SEAM + drivers + gate, resolution 0013 / D5)
- [ ] 5.1 Extract seam (`BrowserBackend`, `RenderedPage`, `BackendCookie`, `RenderOutcome`) + both drivers + launchers.
- [ ] 5.2 Keep `subresource_blocks`; rewrite docstring to the observation, not a2web's conclusion (D5).
- [ ] 5.3 **Port the skip-forbidden real-launch gate** into shelf CI (both engines launch a real page, assert render; missing binary FAILS). Port a2web's `browser-gate` pattern, don't reinvent.
- [ ] 5.4 Carry the standing fake-fidelity contract (`test_fake_config_matches_real_add_argument`).
- [ ] 5.5 Boundary test; D6 gate; `make check`; tag `any-browser-v0.1.0`; push; repoint a2web (keep `select_backend*` + mapping home).

## 6. Close the loop (resolution 0009)
- [ ] 6.1 `use-cases/a2web--<pkg>.toml` per promotion.
- [ ] 6.2 `ledger/00NN-<slug>.toml` `delivery` row per promotion; separate `verdict` row per repoint that held.
- [ ] 6.3 `make catalog` (stale derived README lies).
- [ ] 6.4 `make check` green; merge `work/a2web` → `main`; push. Remove worktree + merged branch.
- [ ] 6.5 Report: candidate → verdict → action table + what the shelf gained.
