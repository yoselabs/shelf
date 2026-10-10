"""Tags a Gherkin suite reads rather than runs, as a pytest plugin (entry point ``pytest11``).

- ``@spec:<capability>`` and ``@bug:<id>`` are traceability. They are read from the feature
  files and are not pytest markers, so ``--strict-markers`` does not ask for them to be
  registered.
- ``@known_bug:<id>`` marks a scenario that states the right behaviour while the code still
  gets it wrong: a strict expected failure. The day the bug is fixed the scenario passes, the
  run fails, and the tag must go.
- ``@pending`` marks a scenario whose steps are not written yet: it is collected and reported
  as skipped. A missing step in a scenario without the tag still fails.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

#: Tag prefixes that only record where a scenario comes from.
TRACE_PREFIXES: Final = ("spec:", "bug:")
KNOWN_BUG: Final = "known_bug:"
PENDING: Final = "pending"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", f"{PENDING}: a scenario whose steps are not written yet; reported as skipped (bdd-tags)")


# First, ahead of pytest-bdd's own hook, which turns every tag into a marker: plugin load order
# is not fixed, and a `@spec:` marker then fails `--strict-markers` at collection.
@pytest.hookimpl(tryfirst=True)
def pytest_bdd_apply_tag(tag: str, function: Callable[..., object]) -> bool | None:
    """Traceability tags are swallowed; ``known_bug:`` becomes a strict xfail; any other tag is a marker."""
    if tag.startswith(TRACE_PREFIXES):
        return True
    if tag.startswith(KNOWN_BUG):
        pytest.mark.xfail(reason=f"{tag}: not fixed yet", strict=True)(function)
        return True
    return None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """A ``@pending`` scenario is reported as skipped."""
    for item in items:
        if item.get_closest_marker(PENDING) is not None:
            item.add_marker(pytest.mark.skip(reason="pending: steps not implemented"))


__all__ = ["KNOWN_BUG", "PENDING", "TRACE_PREFIXES", "pytest_bdd_apply_tag", "pytest_collection_modifyitems", "pytest_configure"]
