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

import asyncio
import os
import warnings
from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, settings

if TYPE_CHECKING:
    from collections.abc import Iterator

# A git hook (pre-push runs `just check`) exports the variables that locate its repository. Inherited, they point
# every test's `git -C <tmp repo>` at the shelf itself: from a worktree, guard tests wrote into its README and
# pyproject (2026-10-12). Tests make their own repos, so none of these may reach them.
for _var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY"):
    os.environ.pop(_var, None)

# A task-loop run hands every child its hooks dir as core.hooksPath through git's env config (GIT_CONFIG_COUNT and
# GIT_CONFIG_KEY_n/VALUE_n). Inherited, `tl pre-push` judged the `git push` of a test's own temp repo and refused it
# (packages/any-gate/tests/test_changed_files.py, 2026-11-05). The numbered entries go; GIT_CONFIG_GLOBAL and _NOSYSTEM stay, they isolate.
for _var in [v for v in os.environ if v == "GIT_CONFIG_COUNT" or v.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))]:
    os.environ.pop(_var, None)

# too_slow times input generation by the wall clock. With one pytest worker per core
# (`just test`, pytest-xdist) a cold first draw on a loaded machine trips it -- a red
# caused by the machine, not the change.
_NOT_TIMED = [HealthCheck.too_slow]
settings.register_profile("default", suppress_health_check=_NOT_TIMED)
settings.register_profile("ci", derandomize=True, suppress_health_check=_NOT_TIMED)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

# `pytester` runs a small suite in a sandbox; bdd-tags proves its plugin hooks with it.
# Declared here because pytest accepts `pytest_plugins` only in the rootdir conftest.
# `tools.blueprint_fitness` is the blueprint registry fitness (W2): every checkpoint seen passing and not passing over a
# whole blueprint-suite run.
pytest_plugins = ["pytester", "tools.blueprint_fitness"]


@pytest.fixture(autouse=True)
def _close_orphan_event_loop() -> Iterator[None]:
    """Close the clean loop pytest-asyncio leaves installed after an async test.

    pytest-asyncio (0.26, `asyncio_mode = "auto"`) installs a fresh loop after every async test and never closes it. A later sync
    test that calls `asyncio.run()` ends with `set_event_loop(None)`, dropping the last reference to that loop; it is then collected at
    an arbitrary point and `BaseEventLoop.__del__` raises "unclosed event loop" (and its AF_UNIX self-pipe) inside whichever test runs
    then. With `filterwarnings = ["error"]` that failed a different innocent test on every full run. This fixture is outermost, so its
    teardown runs after pytest-asyncio's own and closes the loop before an `asyncio.run` can orphan it.
    """
    yield
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            return
    if not loop.is_running() and not loop.is_closed():
        loop.close()
