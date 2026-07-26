"""Test fixture — plugin that reports Unavailable; must NOT appear in registry."""

from __future__ import annotations

from plugin_surface import PluginManifest, Unavailable

from _fixture_surface.widget_alpha import Widget


def _build(_ctx: object) -> Widget | Unavailable:
    return Unavailable("test: capability missing")


MANIFEST = PluginManifest(name="gamma", protocol=Widget, factory=_build)
