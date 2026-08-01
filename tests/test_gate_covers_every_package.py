"""The gate must actually run every package's tests.

`testpaths` in the root `pyproject.toml` is hand-maintained, and a hand-maintained
list of what to check is the classic silent-enforcement loss: nothing fails when
an entry is *missing*, so a package can ship a green `make check` while its own
suite has never been executed. That is strictly worse than having no suite —
a green gate is read as evidence.

It happened. On 2026-08-01, **8 of 26** package suites were absent from the list
(`a2effect` — 12 test files — `atomic-io`, `dom-schema`, `duckdb-sidecar`,
`lean-wire`, `managed-region`, `mcp-result-wire`, `page-tsv`), together **174
tests running in no gate at all**. All 174 passed when finally run, so nothing
had shipped broken; the loss was that nothing would have *told* us. It surfaced
only because a promotion added six tests and the root collection count did not
move.

The failure is directional, which is why this test is worth its lines: a package
gaining tests nobody runs is invisible, while this assertion is loud and names
the missing path.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = _ROOT / "packages"

#: A floor, not a target. Any walk that finds nothing passes every `set()`
#: comparison below and reads exactly like a healthy one — the anti-vacuity rule
#: this repo applies to its own architecture guards applies to this one too.
_MIN_PACKAGES_WITH_TESTS = 20


def _declared_testpaths() -> set[str]:
    cfg = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(cfg["tool"]["pytest"]["ini_options"]["testpaths"])


def _package_test_dirs() -> set[str]:
    return {str(p.relative_to(_ROOT)) for p in _PACKAGES.glob("*/tests") if p.is_dir()}


def test_the_walk_found_the_packages() -> None:
    """Non-vacuity. An empty `packages/` would satisfy every assertion below."""
    found = _package_test_dirs()
    assert len(found) >= _MIN_PACKAGES_WITH_TESTS, f"only {len(found)} package test dirs found — is the walk pointed at the right tree?"


def test_every_package_suite_is_in_the_gate() -> None:
    """THE regression. A suite absent from `testpaths` is never run."""
    missing = sorted(_package_test_dirs() - _declared_testpaths())
    assert missing == [], (
        "these package test suites exist on disk but are NOT in `testpaths`, so "
        f"`make check` never runs them: {missing}. Add them to the root pyproject.toml."
    )


def test_the_gate_lists_no_path_that_does_not_exist() -> None:
    """The other direction: a renamed or deleted suite left behind in the list.

    pytest does not fail on a `testpaths` entry that no longer exists, so a stale
    entry is as quiet as a missing one — and it makes the list *look* longer than
    the coverage it buys.
    """
    stale = sorted(p for p in _declared_testpaths() if not (_ROOT / p).is_dir())
    assert stale == [], f"`testpaths` names directories that do not exist: {stale}"
