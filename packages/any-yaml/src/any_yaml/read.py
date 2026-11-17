"""Reads: plain data, YAML 1.2 (so `on:` and `yes` stay words, never booleans)."""

import functools
from types import MappingProxyType

from ruamel.yaml import YAML


def load(text: str) -> object:
    """A fresh copy, safe to change. Raises YAMLError on malformed text."""
    data: object = YAML(typ="safe", pure=True).load(text)
    return data


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@functools.lru_cache(maxsize=8192)
def read(text: str) -> object:
    """Parsed once per distinct content in this process; read-only: mappings are `MappingProxyType`, lists tuples,
    so the shared cached value cannot be changed by one caller under another. Use `load` for a copy to change."""
    return _freeze(load(text))


__all__ = ["load", "read"]
