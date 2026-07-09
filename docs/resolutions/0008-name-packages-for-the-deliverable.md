# 0008 — Name a promoted package for what it delivers, not for its origin

- **Status:** decided (2026-07-09)
- **Expires:** 2027-01-09 (re-justify once enough promotions exist to check whether the rule held)
- **Track:** governance / the promotion model
- **Distilled into:** agent-loop.md WORKFLOW: PROMOTE, step 3

## The fork

`PROMOTE` step 3 says "extract the code into `packages/<name>/`" and gives no guidance on choosing
`<name>`. In practice, promoted packages carry the origin app's internal module/folder name forward
verbatim by default (`content_extract` → `content-extract`, `html_fragment` → `html-fragment`), and
sometimes get deliberately renamed (`record_extract` → `record-mine`, `cookie_store` →
`browser-cookies`). That inconsistency is invisible until someone asks "why is this named that?" —
surfaced 2026-07-09 auditing `convert-md` / `content-extract` / `html-fragment`'s layering.

## The rule

**Name a package for what it delivers to any future consumer, never for the app it happened to be
extracted from.** The origin app's internal name is a historical accident of *where the code was
first needed* — it carries zero information for a consumer who has never seen that app. A promoted
name should be readable as "what does this do" cold, on the catalog, with no origin context.

This does **not** forbid keeping the origin name — it forbids keeping it *by default, uninspected*.
`content-extract` keeps a2web's original folder name because that name already passed the test (it
describes the deliverable: "extract [structured] content [from a page]"). `record-mine` and
`browser-cookies` were renamed because their origin names (`record_extract`, `cookie_store`) didn't.
Both are the same rule, applied — the coincidence of keeping a name is not evidence the rule was
skipped.

**The test, applied at `PROMOTE` step 3, before naming `packages/<name>/`:** read the candidate name
as if you are a consumer who has never seen the origin app. Does it say what the package delivers?
If yes, keep it (even if it matches the origin folder). If it only makes sense with origin-app
context (a product codename, an internal jargon term, a name that only disambiguates *within* that
app's own module tree), rename it before the tag ships — renaming after adoption is a breaking
change for every consumer's dependency line.

## What changes (propagated)

- **agent-loop.md `PROMOTE` step 3** gains the naming test as an explicit sub-step, run once, at
  extraction time — before the first tag, while renaming is still free.

## The risk, named

This is a judgment call, not a mechanical check — "does this name survive without origin-app
context" has no automated test. The risk is inconsistent application (the exact problem this
resolution responds to) recurring anyway. Accepted: cheap to catch and cheap to fix (rename +
retag) as long as it's caught before a consumer's `pyproject.toml` pins the old name — which is why
the test runs at `PROMOTE`, before the first tag, not after.
