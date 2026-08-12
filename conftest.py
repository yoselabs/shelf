"""Root pytest bootstrap: registers Hypothesis's seeding policy for CI vs local runs.

shelf-2xb's "honest complication": Hypothesis reseeds its random exploration on every
run by default, so CI would explore a different input space than any local run —
`.hypothesis/`'s example database is self-gitignored (`docs/runbooks/property-based-testing.md`),
so nothing carries a discovered failure between CI runs anyway. Left alone, that means a
property suite can surface a genuinely new, previously-unseen boundary on ANY commit's CI
run, including one that never touched the package in question — "an unrelated PR turns
red" is exactly the failure mode this file exists to prevent.

**Local runs stay randomized** (the default profile, unchanged): the runbook's own
"rerun a property file 5-8 times before trusting a green result" workflow depends on that
exploration to actually find new boundaries during authoring — a found boundary gets
pinned as an explicit `@example(...)` (see `timefmt`'s `ms=1450`), which is how the
project's convention already turns "randomly discovered" into "permanently checked".

**CI runs derandomized** (`HYPOTHESIS_PROFILE=ci`, set in `.github/workflows/check.yml`):
a fixed seed means every CI run explores the identical sequence of examples for a given
test, so a failure is reproducible and would have failed on the PREVIOUS commit too — it
can never spring newly on an innocent, unrelated change. This trades away CI's own power
to discover new boundaries (authoring already covers that) for the one property CI
actually needs: never blocking a PR for a reason unrelated to what it touched.
"""

from __future__ import annotations

import os

from hypothesis import settings

settings.register_profile("default")
settings.register_profile("ci", derandomize=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))
