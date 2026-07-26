"""Test fixture — second plugin, higher priority (sorts before alpha)."""

from __future__ import annotations

from plugin_surface import PluginManifest, Unavailable

from _fixture_surface.widget_alpha import Widget


class BetaWidget:
    name = "beta"


def _build(_ctx: object) -> Widget | Unavailable:
    return BetaWidget()


MANIFEST = PluginManifest(name="beta", protocol=Widget, factory=_build, priority=1)
