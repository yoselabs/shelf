"""A scenario tagged ``@real_only`` names a gap of FakeRepo (the feature says which); it runs on the real git only."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    gone = [
        item
        for item in items
        if item.get_closest_marker("real_only") is not None
        and getattr(getattr(item, "callspec", None), "params", {}).get("implementation") == "fake"
    ]
    if gone:
        config.hook.pytest_deselected(items=gone)
        items[:] = [item for item in items if item not in gone]
