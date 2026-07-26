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

## 2. llm-wobble  ✅ DONE 2026-07-26 (tag llm-wobble-v0.1.0)
- [x] 2.1 Extracted `packages/llm_extract/wobble/_internal.py` → `packages/llm-wobble/`.
      D2 note was stale (code emitted on `getLogger("a2web")`, not `"a2kit"`): the real
      fix is logger INJECTION (default `getLogger("llm_wobble")`, `logger=` override),
      matching plugin-surface. Dropped the `apply_policy` back-compat shim; the suite
      exercises the real funnel (STRICT miss → `ParseError`, `WobbleSkip` propagates).
- [x] 2.2 `_policies.py` stays in a2web (product); now imports `WobblePolicy`/
      `WobbleTolerance` from `llm_wobble`.
- [x] 2.3 Acceptance suite ported (`test_llm_wobble.py`, 17 assertions) + boundary
      test. **D6 foreign-soil gate PASS**: 17/17 against the installed wheel in a
      clean venv (no repo deps).
- [x] 2.4 `make check` green (367 passed, 88.63% — also fixed a real gap: neither
      plugin-surface NOR llm-wobble was in pytest `testpaths`, so promotion #1's
      tests never ran under the gate; both registered now). Tagged, pushed, a2web
      repointed (`5fd4467`; gate 1237 passed / 90.22% / 39 arch tests).

## 3. anyllm.cost  ✅ DONE 2026-07-26 (tag anyllm-v0.5.0)
- [x] 3.1 Added `anyllm.cost` (`CostPolicy`, `assert_within_budget`, `with_cost_guard`,
      `CostViolation`, `DEFAULT_COST_POLICY`), keyed on `ProviderName` (D4). Verified
      with foreign evidence that a2web's three providers ARE anyllm adapters carrying a
      canonical `ProviderName` as `.name` (anthropic→anthropic-api, claude-code→
      claude-code-sdk, openai_compatible→openai-compatible) — so `with_cost_guard`
      reads `provider.name` and drops the separate manifest-id arg. The old a2web
      "`.name` can vary" comment was stale (pre-v0.3.0 enum union). The subscription-vs-
      metered distinction is a property of the BACKEND, so the enum is the right key.
- [x] 3.2 Monotonicity (resolution 0007): v0.4.0→v0.5.0, purely additive — new `cost`
      submodule + 5 top-level re-exports, removed nothing. (Also: `FBT` added to
      `packages/*/tests` per-file-ignores — boolean parametrize params are test noise.)
- [x] 3.3 Ported the acceptance suite (`tests/test_cost.py`, 16 assertions incl.
      StrEnum-value equality + unknown-provider deny). Boundary auto-covered by the
      existing `test_anyllm_boundary.py` walk. **D6 foreign-soil gate PASS**: 16/16
      against the installed wheel in a clean venv (only anyllm present, no SDK extras).
- [x] 3.4 `make check` green (383 passed, 88.71%). Tagged `anyllm-v0.5.0`, pushed.
      a2web repointed: imports from `anyllm` directly (no binding needed — the guard has
      no logger/policy injection); `packages/llm_cost_guard.py` removed; a2web keeps a
      BINDING test that its provider names map onto the default policy. a2web gate 1226
      passed / 90.19% / 39 arch tests.

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
