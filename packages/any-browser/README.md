# any-browser

Stop caring which headless browser renders a JavaScript page. One
`BrowserBackend` seam sits over two engine *families* — the Playwright API
(Camoufox, Patchright) and raw CDP (zendriver) — so a consumer says "render this
URL with these cookies, within this budget" and never learns which driver
answered.

```python
from any_browser import BackendCookie, PlaywrightBackend, RenderOutcome, patchright_launcher

async with PlaywrightBackend(patchright_launcher, name="patchright") as backend:
    page = await backend.render(
        "https://example.com/search?q=widgets",
        cookies=[BackendCookie("sid", "abc", "example.com", "/", None, True, True, "lax")],
        budget_s=20.0,
        js_heavy=True,
    )

if page.outcome is RenderOutcome.ok:
    print(page.html, page.final_url, page.status_code)
else:
    print("no render:", page.outcome, page.detail)   # timeout / error / unavailable
```

## Design

- **Consumer-free seam.** `BrowserBackend` and its value objects (`RenderedPage`,
  `BackendCookie`, `RenderOutcome`) carry no app types. The caller converts its
  own cookie type into `BackendCookie` before a render and maps
  `RenderOutcome`/`RenderedPage` into its own result types after — so the same
  backend drops into any app.
- **Failure is data, not an exception (the any-\* state-boundary law).** `render`
  never raises for a routine failure. A timeout, a navigation/driver error, or a
  missing engine all come back as a `RenderedPage` carrying the matching
  `RenderOutcome` (`timeout` / `error` / `unavailable`). The consumer reads the
  channel; it never guesses at an exception type.
- **Engines are optional.** Install the `patchright` and/or `zendriver` extra for
  the engine you want; a missing engine surfaces as `RenderOutcome.unavailable`,
  never an `ImportError` at import time — so you can ship the seam and degrade
  gracefully where no engine is present.
- **Two families, one interface.** `PlaywrightBackend` runs any Playwright-API
  engine via a `launch_fn` (per-host LRU context pool, an idle reaper that bounds
  resident browser processes on a long-lived server, and opt-in driver-stderr
  capture through an injected async sink). `ZendriverBackend` drives Chromium
  directly over CDP (per-render launch), for the SPAs a Playwright drop-in fails
  to read — proof the seam spans engine families, not just one driver API.
- **`subresource_blocks` is an observation, not a verdict.** `RenderedPage`
  reports how many page subresources (XHR/fetch) returned a challenge status
  (401/403/429) during the render. This package attaches no meaning to the
  count; a consumer may read it as evidence (e.g. that a "0 results" shell had
  its data API blocked), but that interpretation lives entirely in the consumer.
- **Logger injected.** Scroll-retry diagnostics emit on an injected
  `logging.Logger` (default `logging.getLogger("any_browser")`); pass your own to
  route them into your logging substrate.

## Engine binaries

The Python extras pull the driver libraries; the browser *binaries* are a
separate fetch. For Patchright: `patchright install chromium`. In a container,
point zendriver at that same managed Chromium with `PLAYWRIGHT_BROWSERS_PATH`
(zendriver otherwise auto-discovers a *system* Chrome that a slim image lacks),
or override explicitly with `ANY_BROWSER_EXECUTABLE_PATH`.

## Verification

The engine adapters are covered two ways beyond the fake-driver unit tests:

- **A skip-forbidden real-launch gate** (`tests/test_browser_smoke.py`, the
  `browser` pytest marker) launches each real engine against a local
  JS-rendering page and asserts a render. It *skips* on a dev machine with no
  Chromium, but in an environment that sets `SHELF_REQUIRE_BROWSER=1` a
  non-launching engine is a hard **failure** — the one place obligated to prove
  the browser actually comes up. (A silent skip in the controlled environment is
  exactly how a robust rung once shipped dead-on-launch while every check stayed
  green.)
- **A fake-fidelity contract** (`test_fake_config_matches_real_add_argument`)
  re-checks the hand-written driver `Config` fake against the *real installed*
  library every commit, so a permissive fake can never drift laxer than reality.
