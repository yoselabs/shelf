# any-browser — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.3.0: breaking  ⇒  `BrowserBackend.render(url, *, cookies, budget_s, js_heavy, scroll_to_stable=False)` loses `scroll_to_stable`; new `BrowserBackend.render_listing(url, *, cookies, budget_s, js_heavy)` (the old `scroll_to_stable=True`: scroll until the HTML stops growing); on `PlaywrightBackend` and `ZendriverBackend`; a Backend implementation must add `render_listing`
- 0.2.0: `ZendriverBackend(*, name="zendriver", page_budget_s=30)`  ⇒  `ZendriverBackend(*, env, name="zendriver", page_budget_s=30)` (`env` required): `ANY_BROWSER_EXECUTABLE_PATH` and `PLAYWRIGHT_BROWSERS_PATH` are read from it, not from `os.environ`
