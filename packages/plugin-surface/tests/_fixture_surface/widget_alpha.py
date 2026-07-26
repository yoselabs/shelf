"""Test fixture — minimal plugin module declaring a MANIFEST."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from plugin_surface import PluginManifest, Unavailable


@runtime_checkable
class Widget(Protocol):
    name: str


class AlphaWidget:
    name = "alpha"


def _build(_ctx: object) -> Widget | Unavailable:
    return AlphaWidget()


MANIFEST = PluginManifest(name="alpha", protocol=Widget, factory=_build)
