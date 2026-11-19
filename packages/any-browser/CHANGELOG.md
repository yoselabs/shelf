# any-browser — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.2.0: `ZendriverBackend(*, name="zendriver", page_budget_s=30)`  ⇒  `ZendriverBackend(*, env, name="zendriver", page_budget_s=30)` (`env` required): `ANY_BROWSER_EXECUTABLE_PATH` and `PLAYWRIGHT_BROWSERS_PATH` are read from it, not from `os.environ`
