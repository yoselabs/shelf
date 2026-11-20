"""One module per concern; importing a module registers its checks."""

from __future__ import annotations

import importlib

MODULES = (
    "gate",
    "backlog",
    "knowledge",
    "secrets",
    "hooks",
    "stack",
    "python_pin",
    "cli_parse",
    "shell",
    "uv_tool",
    "tool_pins",
    "owners",
    "shelf_sources",
    "framework",
    "agents",
)


def load() -> None:
    """Import every concern module, so its checks join the registry."""
    for name in MODULES:
        importlib.import_module(f"{__name__}.{name}")
