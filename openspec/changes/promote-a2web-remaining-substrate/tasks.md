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

## 4. llm-cache  ✅ DONE 2026-07-26 (tag llm-cache-v0.1.1)
- [x] 4.1 Extracted `packages/llm_extract/cache.py` → `packages/llm-cache/`. D3: `get`/`put`
      speak `anyllm.Completion` (a hit is a drop-in for a call — original cost/tokens/latency
      ride along). Generalised the key: a2web's 4-part composite (content_hash, ask_hash,
      model_id, template_name) collapses to an opaque `(key, model)` — the package is
      policy-free, the caller computes the key via `make_key(*parts)`. Connection-injected
      (`aiosqlite.Connection`, from `sqlite-resource`'s `.conn`); owns only its table.
- [x] 4.2 Boundary test (`test_boundary_llm_cache.py`) + acceptance suite (`test_llm_cache.py`,
      the cache-primitives half of a2web's old test, adapted). **D6 gate PASS**: 7/7 against
      the installed wheels in a clean venv (llm-cache + anyllm + aiosqlite only).
- [x] 4.3 `make check` green (392 passed, 88.95%). Tagged; pushed; a2web repointed.
      **v0.1.1 hotfix**: dropped the package's dev-only `[tool.uv.sources]` (a published
      package's uv.sources leaks into the consumer's resolution). Registered
      `packages/llm-cache/tests` in root testpaths (the gate-gap pattern).
      a2web adoption surfaced a WORKSPACE-SOURCE LEAK (documented in a2web's pyproject +
      §6.5 report): the shelf root force-sources anyllm (dev group needs it) and uv applies
      that to git consumers, colliding with a2web's own anyllm pin. Fix on a2web's side —
      it sources anyllm THROUGH the shelf workspace at the llm-cache tag rather than pinning
      it independently. a2web gate 1220 passed / 90.12% / 39 arch.

## 5. any-browser  ✅ DONE 2026-07-26 (tag any-browser-v0.1.0)
- [x] 5.1 Extracted seam (`BrowserBackend`, `RenderedPage`, `BackendCookie`,
      `RenderOutcome`) + BOTH drivers (`PlaywrightBackend`, `ZendriverBackend`) +
      launchers (`patchright_launcher`, `camoufox_launcher`, `chromium_launch`).
      Engines are optional extras (`[patchright]`, `[zendriver]`); a missing one
      degrades to `RenderOutcome.unavailable`, never an import crash.
- [x] 5.2 Kept `subresource_blocks`; docstring reworded to the OBSERVATION
      (subresources returning a challenge status during render) — the "walled-API
      fake-empty" CONCLUSION stays in a2web's `actions/terminal.py` + `empty.py` (D5).
      Also: logger INJECTED (default `getLogger("any_browser")`) per D1/D2; the
      a2web-named `A2WEB_BROWSER_EXECUTABLE_PATH` override renamed to the neutral
      `ANY_BROWSER_EXECUTABLE_PATH` (consumer-name leak).
- [x] 5.3 Ported the skip-forbidden real-launch gate: `browser`-marked
      `test_browser_smoke.py` launches each real engine against a local JS page and
      asserts a render; the pure skip→fail policy (`browser_unavailable_policy`) is
      pinned in the DEFAULT gate by `test_browser_gate_policy.py`; `make test-browser`
      + `SHELF_REQUIRE_BROWSER=1` make a non-launching engine a hard FAIL. Marker
      registered; `-m "not browser"` deselects it by default. (5.2c note: no
      zendriver-diagnose-or-drop was needed — the fidelity contract + the ported
      launch gate + the diagnostic probe already cover the dead-rung failure mode;
      the a2web correlated-witness workaround was NOT carried over.)
- [x] 5.4 Carried the fake-fidelity contract (`test_fake_config_matches_real_add_argument`):
      re-checks the hand-written zendriver `Config` fake against the REAL installed
      lib every commit. Added `zendriver` to the shelf dev group so it RUNS (not
      importorskip-away); patchright stays out (heavy vendored Chromium — only the
      browser lane installs it).
- [x] 5.5 Boundary test (`test_boundary_any_browser.py`); **D6 foreign-soil gate
      PASS** (47/47 against the installed wheel in a clean isolated venv, zendriver +
      pytest only, `any_browser` from site-packages); `make check` green (441 passed,
      86.09%). Tagged, pushed. a2web repointed: `packages/browser_backends/` deleted,
      imports → `any_browser`, both driver test files moved to the shelf acceptance
      suite, `select_backend*`/manifests/rung-split/mapping kept home, patchright
      manifest injects `get_logger()`, `[browser]` extra pulls
      `any-browser[patchright,zendriver]`, `tach.toml` module dropped. a2web gate
      1173 passed / 90.49% / 37 arch.

## 6. Close the loop (resolution 0009)  ✅ DONE 2026-07-27
- [x] 6.1 Four new `use-cases/a2web--<pkg>.toml` (plugin-surface, llm-wobble, llm-cache,
      any-browser). anyllm.cost needed none — a2web already has `a2web--anyllm.toml`;
      updated it (and the anyllm catalog entry) to name the cost guard + bump v0.2.0→v0.5.0
      (the catalog release had drifted — v0.3.0/v0.4.0 shipped without a bump).
- [x] 6.2 Ten ledger rows 0053–0062: a `delivery` + a `verdict` (adopted) row per promotion.
      anyllm.cost's delivery is event="delivery"/release=anyllm-v0.5.0 (an EVOLUTION, like 0032),
      not a new-package delivery.
- [x] 6.3 `make catalog` regenerated all three derived READMEs; four new catalog manifests
      (plugin-surface/llm-wobble/llm-cache/any-browser) added — each has an active use-case so
      `test_no_orphaned_software` holds.
- [x] 6.4 `make check` green (441 passed, 86.09%); merged `work/a2web` → `main`; pushed.
      Worktree + merged branch removed.
- [x] 6.5 Report delivered (candidate → verdict → action table + what the shelf gained).
