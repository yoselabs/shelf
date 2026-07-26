# Design

## D1 — plugin-surface: inject the logger, don't hardcode a name

`_plugin.py` logged via a2web's `log_debug`/`log_warning` (the `a2web` logger).
A generic package cannot import a consumer, and must not hardcode a consumer's
logger name (the exact anti-pattern `llm-wobble` carries with `"a2kit"`). Two
options: (a) a package-local logger the consumer configures, or (b) inject the
logger. Chose **(b)** — `load_surface(..., *, logger=None)` defaulting to
`logging.getLogger("plugin_surface")`. a2web passes its own logger, so the record
shape (`extra={"fields": payload}`) and its stdio-safety discipline
(`propagate=False`, NullHandler floor — a2web serves MCP over stdio) are both
preserved, at 6 call sites. `settings_prefix` is dropped: it was a no-op reserved
field, never set by any manifest.

## D2 — llm-wobble: parameterize the logger; policy tables stay home

Same logger seam as D1 (replace the hardcoded `getLogger("a2kit")`). The
`WobblePolicy` *mechanism* (STRICT/DERIVE/DEFAULT/SKIP + the funnel + the
`Wobbled` NewType) is generic and promotes; the concrete per-field policy tables
in a2web's `_policies.py` are product and stay in a2web (they describe a2web's LLM
contracts). The single `llm_wobble` structured log key stays as the recovered-
wobble signal, emitted through the injected logger.

## D3 — llm-cache: return `anyllm.Completion`

The extraction cache stored a bespoke row whose fields already match
`anyllm.Completion`. Returning `anyllm.Completion` removes a boundary type and
lets the cache compose cleanly with `anyllm` above `sqlite-resource`. Shape
change at the extraction seam; a2web adapts at repoint.

## D4 — anyllm.cost: key on `ProviderName`, monotonic evolve

The cost guard (ADR-0016 in a2web: never bill metered Anthropic in dev/eval/bench)
is generic budget enforcement over `(provider, model)`. Promote it as an
`anyllm.cost` submodule beside `anyllm`'s existing `PromptParts`/provider surface,
keyed on `anyllm.ProviderName` (a `StrEnum`), NOT a2web's manifest strings —
otherwise the guard drifts from the provider set it guards. Resolution 0007
monotonicity: `anyllm` exposes more (`CostPolicy`, `assert_within_budget`,
`with_cost_guard`, `CostViolation`) and removes nothing → new tag, old stays.

## D5 — any-browser: promote the drivers NOW, gate travels with them (resolution 0013)

The earlier plan held the drivers off the shelf until a shelf-side real-launch
gate existed, on the (correct) witness-rule observation that a promoted driver
with only a hand-written fake + skip-on-missing-binary smoke ships a blind spot —
that is how a2web's own robust rung sat dead-on-launch while green. Resolution
0013 reframes: that conflated *is-the-shape-right* (resolved only by a second
consumer bending the `BrowserBackend` seam — which requires it be on the shelf)
with *is-it-verified* (an obligation that travels with the code). So:

- **Promote the full package**: `BrowserBackend` Protocol + `RenderedPage` /
  `BackendCookie` / `RenderOutcome` + BOTH drivers (Playwright-API rung, raw-CDP
  rung) + launchers.
- **Port the real-launch gate in the same change**: a shelf CI lane that launches
  both engines against a real page and asserts a render, `skip-on-missing-binary
  FORBIDDEN` (a2web's `browser-gate` + `A2WEB_REQUIRE_BROWSER=1` pattern:
  `test_browser_smoke.py::browser_unavailable_policy`, pinned by
  `test_browser_gate_policy.py`). Port it; don't reinvent it.
- **Carry the standing fake-fidelity contract** (a2web
  `test_zendriver_backend.py::test_fake_config_matches_real_add_argument`): the
  hand-written driver `Config` fake is re-checked against the real installed lib
  every commit, so it cannot drift laxer than reality (the dead `--no-sandbox`
  rung).
- **Stays home (product)**: `select_backend*`, manifest gating, the fast/robust
  rung split policy, and the `RenderOutcome → Verdict/OperatorHint` mapping.
- **Keep** `RenderedPage.subresource_blocks`, but the promoted docstring describes
  the *observation* (subresources returning a challenge status during render),
  not a2web's "walled-API fake-empty" *conclusion* (that meaning stays in a2web
  `actions/terminal.py` + `actions/empty.py`).

## D6 — foreign-soil install gate per package (THE gate, resolution-of-record)

Before each tag is cut: install the package from the worktree/tag into a clean
env with none of a2web's incidental deps and run its acceptance suite against the
*installed artifact* (not the source tree). Kills the works-in-monorepo /
broken-as-artifact class (undeclared deps, missing `py.typed`, packaging holes,
graceful-absence paths that never run on home soil). Local approximation until
shelf CI carries it: `uv run --with <package> --no-project pytest <tests>` from a
scratch dir. This is the highest expected-loss item — ahead of any endogenous-
oracle concern (a2web `docs/architecture/verification-provenance.md`).
