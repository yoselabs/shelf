---
id: 0008
title: Name packages for the deliverable
statement: Name a promoted package for what it delivers to a consumer who has never seen the origin app, tested before the first tag while renaming is still free.
concerns: [packaging, workflow]
status: accepted
decided_by: owner
updated: 2026-07-09
expires: 2027-01-09
distilled_into: agent-loop.md WORKFLOW: PROMOTE, step 3
---

# 0008 — Name a promoted package for what it delivers, not for its origin

## Decision

**Name a package for what it delivers to any future consumer, never for the app it was extracted
from.** The origin app's internal name is a historical accident of where the code was first needed
and carries no information for a consumer who has never seen that app.

**The test**, run at `PROMOTE` step 3 before naming `packages/<name>/`: read the candidate name as a
consumer who has never seen the origin app. Does it say what the package delivers? If yes, keep it,
even if it matches the origin folder (`content-extract` kept a2web's name because it passed). If it
only makes sense with origin context (a product codename, internal jargon, a name that only
disambiguates inside that app's module tree), rename it before the tag ships: renaming after adoption
breaks every consumer's dependency line. The rule forbids keeping the origin name *by default,
uninspected*, not keeping it; `record_extract` became `record-mine` and `cookie_store` became
`browser-cookies` because their origin names failed.

## Rejected

- **Carrying the origin module/folder name forward by default** (`content_extract`, `html_fragment`
  were kept; others renamed): inconsistent, invisible until someone asks "why is this named that?"
  (surfaced 2026-07-09 auditing `convert-md` / `content-extract` / `html-fragment` layering).

## Risk, accepted

A judgment call with no automated test, so inconsistent application can recur. Cheap to catch and fix
(rename + retag) as long as it is caught before a consumer's `pyproject.toml` pins the old name,
which is why the test runs at `PROMOTE`, before the first tag.

## History

- 2026-07-09: decided; `agent-loop.md` PROMOTE step 3 gained the naming test as an explicit sub-step.
  Expires 2027-01-09 (re-justify once enough promotions exist to check the rule held). Track:
  governance / the promotion model.
