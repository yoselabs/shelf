"""One module per concern; importing a module registers its checks."""

from __future__ import annotations

import importlib

MODULES = ("gate", "backlog")


def load() -> None:
    """Import every concern module, so its checks join the registry."""
    for name in MODULES:
        importlib.import_module(f"{__name__}.{name}")
