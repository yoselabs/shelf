"""One module per concern; importing a module registers its checks."""

from __future__ import annotations

import importlib

MODULES = (
    "gate.gate",
    "beads.backlog",
    "beads.hooks",
    "beads.agents",
    "secrets.secrets",
    "secret_scan.secrets_scanner",
    "git_hooks.hooks",
    "stacks.stack",
    "layout.layout",
    "layout.root_files",
    "layout.one_config",
    "python.python_pin",
    "stacks.cli_parse",
    "shell.shell",
    "uv.uv_tool",
    "mise.tool_pins",
    "stacks.owners",
    "stacks.shelf_sources",
    "frameworks.framework",
    "agents.agents",
)


def load() -> None:
    """Import every concern module, so its checks join the registry."""
    for name in MODULES:
        importlib.import_module(f"{__name__}.{name}")
