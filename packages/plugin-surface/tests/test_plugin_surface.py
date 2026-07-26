"""Unit tests for plugin_surface.load_surface / load_surface_sorted."""

from __future__ import annotations

import logging

import pytest
from _fixture_surface.widget_alpha import Widget
from plugin_surface import PluginManifest, Unavailable, load_surface, load_surface_sorted

_CTX = object()
_SURFACE = "_fixture_surface"


def test_load_surface_returns_available_plugins_only() -> None:
    registry = load_surface(_SURFACE, Widget, _CTX)
    assert set(registry) == {"alpha", "beta"}
    assert registry["alpha"].name == "alpha"
    assert registry["beta"].name == "beta"


def test_load_surface_skips_unavailable_silently() -> None:
    registry = load_surface(_SURFACE, Widget, _CTX)
    assert "gamma" not in registry


def test_load_surface_skips_utility_modules() -> None:
    registry = load_surface(_SURFACE, Widget, _CTX)
    assert "_utility" not in registry
    assert "utility" not in registry


def test_load_surface_sorted_orders_by_priority() -> None:
    pairs = load_surface_sorted(_SURFACE, Widget, _CTX)
    # beta has priority=1, alpha the default 0 → beta first.
    assert [name for name, _ in pairs] == ["beta", "alpha"]


def test_injected_logger_receives_unavailable_debug(caplog: pytest.LogCaptureFixture) -> None:
    log = logging.getLogger("plugin_surface_test.unavail")
    with caplog.at_level(logging.DEBUG, logger=log.name):
        load_surface(_SURFACE, Widget, _CTX, logger=log)
    rec = next((r for r in caplog.records if r.getMessage() == "plugin_unavailable"), None)
    assert rec is not None, "expected a plugin_unavailable debug record on the injected logger"
    # Fields ride on record.fields, never splatted onto the record.
    assert rec.fields["name"] == "gamma"  # ty: ignore[unresolved-attribute] - fields set via logging `extra`
    assert "capability missing" in rec.fields["reason"]  # ty: ignore[unresolved-attribute]


def test_wrong_type_manifest_is_skipped_and_warned(caplog: pytest.LogCaptureFixture) -> None:
    log = logging.getLogger("plugin_surface_test.wrong")
    with caplog.at_level(logging.WARNING, logger=log.name):
        registry = load_surface(_SURFACE, Widget, _CTX, logger=log)
    assert "wrong" not in registry and ("not", "a", "manifest") not in registry.values()
    assert any(r.getMessage() == "plugin_manifest_wrong_type" for r in caplog.records)


def test_plugin_manifest_is_frozen() -> None:
    def factory(_c: object) -> object | Unavailable:
        return object()

    m = PluginManifest(name="x", protocol=object, factory=factory)
    with pytest.raises((AttributeError, TypeError)):
        m.name = "y"  # ty: ignore[invalid-assignment] - asserting the frozen dataclass rejects the write


def test_unavailable_is_named_tuple() -> None:
    u = Unavailable("missing api key")
    assert u.reason == "missing api key"
    assert u[0] == "missing api key"
