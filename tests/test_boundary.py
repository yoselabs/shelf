"""The one invariant: no shelf package may import a consumer app."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.lib.boundary import assert_no_consumer_imports

PACKAGES_DIR = Path(__file__).resolve().parent.parent / "packages"
PACKAGE_SRCS = sorted(PACKAGES_DIR.glob("*/src"))


@pytest.mark.parametrize("pkg_src", PACKAGE_SRCS, ids=lambda p: p.parent.name)
def test_package_has_no_consumer_imports(pkg_src: Path) -> None:
    assert_no_consumer_imports(pkg_src)


def test_shelf_actually_has_packages() -> None:
    # Guard against the parametrize silently collecting zero packages.
    assert PACKAGE_SRCS, "no packages/*/src found — the boundary test would be a no-op"
