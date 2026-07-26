"""Test fixture — a MANIFEST of the wrong type. Must be skipped + warned, never registered."""

from __future__ import annotations

#: Not a PluginManifest — a common mistake (assigning a raw tuple/dict). The
#: loader must reject it loudly (WARNING) and continue, never register it.
MANIFEST = ("not", "a", "manifest")
