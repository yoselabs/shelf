## Why

Onboarding a2web onto the shelf is ~90% complete: thirteen substrate pieces were
promoted and repointed in prior sessions (`a2effect`, `lean-wire`, `http-fetch`,
`sqlite-resource`, `http-cache`, `json-in-html`, `html-fragment`, `record-mine`,
`browser-cookies`, `content-extract`, `anyllm`, `timefmt`, `settings-base`).
Reconciling the live catalog against a2web's `pyproject.toml` (2026-07-26) — not
the stale task lists — leaves **five** in-tree pieces that are generic substrate
with no shelf equivalent. a2web wants to shrink to product-only; these should
live on the shelf where a second consumer can challenge and evolve them.

This change also carries the governance shift that reshapes one of the five.
**Resolution 0013 (promote to be challenged)** — landed in this same branch —
retires the earlier "hold the browser drivers off the shelf until a real-launch
gate exists" stance. Holding forfeits the second-consumer challenge that is the
only thing that ever universalizes an abstraction; the verification obligation
travels *with* the code instead. So the browser drivers promote **now**, with a
skip-forbidden real-launch gate ported into the shelf's own CI in the same change.

## What Changes

1. **`plugin-surface`** ← `a2web/_plugin.py`. The `PluginManifest`/`Unavailable`/
   `load_surface`/`load_surface_sorted` framework. Drop the invented no-op
   `settings_prefix`; inject the logger (default `logging.getLogger("plugin_surface")`)
   so no consumer name is hardcoded and a consumer keeps its logging discipline.
2. **`llm-wobble`** ← `a2web/packages/llm_extract/wobble/`. The JSON-parse funnel
   (`parse_with_policy` / `parse_list_with_policy`, `Wobbled`, `WobblePolicy`).
   Parameterize the hardcoded `logging.getLogger("a2kit")`; leave a2web's product
   policy tables (`_policies.py`) in a2web.
3. **`llm-cache`** ← `a2web/packages/llm_extract/cache.py`, on `sqlite-resource` +
   `anyllm`. Return `anyllm.Completion` rather than a bespoke row.
4. **EVOLVE `anyllm.cost`** ← `a2web/packages/llm_cost_guard.py`. Add a `cost`
   submodule (`CostPolicy`, `assert_within_budget`, `with_cost_guard`,
   `CostViolation`) keyed on `anyllm.ProviderName`, not a2web manifest strings.
   Monotonic (resolution 0007): exposes more, removes nothing.
5. **`any-browser`** ← `a2web/packages/browser_backends/`. The `BrowserBackend`
   Protocol + `RenderedPage`/`BackendCookie`/`RenderOutcome` seam **and** both
   drivers (Playwright-API rung, raw-CDP rung) + launchers — promoted together
   per resolution 0013, with a **skip-forbidden real-launch gate** ported into the
   shelf CI (both engines launch against a real page and assert a render; a
   missing binary FAILS, never skips). a2web's `select_backend*`, manifest gating,
   fast/robust rung split, and `RenderOutcome → Verdict/OperatorHint` mapping stay
   home (product).

## Non-goals

- **Not** re-promoting the thirteen already-shipped packages.
- **Not** promoting a2web product/moat: `block_detector`, `escalation`,
  `proxy_routing`, the fetcher orchestration, handler domain logic, and
  `llm_extract`'s `extractor`/`judge`/`prompts`/`router_payload`.
- **Not** promoting `structured-data-md` — `json-in-html` already covers the
  extraction; the normalization gap (`json-in-html` evolve) is deferred pending
  boundary design (a2web change `shelf-sweep-promotions` Q3).
- a2web-side repoints (add pin, delete in-tree copy, `uv lock`, imports, green
  gate, ledger) are tracked in the **a2web** change `shelf-sweep-promotions`; this
  change owns the shelf-side landings (extract, gate, tag, catalog, ledger).
