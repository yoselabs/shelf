"""Plugin manifest framework — one declarative shape every extension point converges on.

**Stop caring how an app discovers and wires its plugins.** Each plugin lives as
a no-side-effects module exporting one ``MANIFEST = PluginManifest(...)`` constant.
:func:`load_surface` walks a package path, imports every module under it, reads
each ``MANIFEST``, calls the factory with a caller-supplied *context*, and returns
a ``dict[str, T]`` of ready-to-use instances. A factory that returns
:class:`Unavailable` is dropped **silently** before it reaches the registry — the
"not configured" state (no API key, no Keychain access, an optional engine
absent) never propagates downstream, so consumer code only ever sees the plugins
that actually loaded.

The design (inspired by Dagster Components, Litestar ``Provide``, and VS Code
contribution points): the *mechanism* of discovery + graceful absence is generic;
the *context* passed to each factory (a settings object, a richer construction
struct) belongs to the app and is treated opaquely here.

Logging is injected, never assumed: pass ``logger=`` to route diagnostics onto
your app's own logger (and keep its handler/propagation discipline intact); omit
it and a package-local ``logging.getLogger("plugin_surface")`` is used. Diagnostic
fields ride on ``record.fields`` (``extra={"fields": {...}}``), never splatted onto
the record — a flat splat collides with reserved ``LogRecord`` attribute names.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, NamedTuple, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

_DEFAULT_LOGGER = logging.getLogger("plugin_surface")


class Unavailable(NamedTuple):
    """Sentinel returned by a plugin factory when its capability is missing.

    Not an exception — unavailability at boot is *expected* (no API key, no
    Keychain access, an optional engine not installed). Returning a value forces
    the call site to handle it; :func:`load_surface` drops Unavailable entries
    before they reach the registry, so consumer code never sees them.
    """

    reason: str


@dataclass(frozen=True, slots=True)
class PluginManifest(Generic[T]):
    """One plugin's registration shape.

    Exported as ``MANIFEST = PluginManifest(...)`` at the bottom of each plugin
    file. :func:`load_surface` reflects on the module to find it.
    """

    name: str
    """Stable lookup key. Used by consumer code to pick a plugin (e.g. ``registry["anthropic"]``)."""

    protocol: type[T]
    """The SPI this plugin implements. Used to filter manifests when multiple
    plugin surfaces share a directory (rare; allowed)."""

    factory: Callable[..., T | Unavailable]
    """Capability-aware constructor. Receives the per-surface construction
    context passed to :func:`load_surface`. Returns either an instance of
    ``protocol`` or ``Unavailable(reason)``. The caller is responsible for passing
    the right context type for the surface; per-surface typing is enforced at the
    consumer seam, not on this generic field."""

    requires: tuple[str, ...] = ()
    """Documentation-only: capability keys this plugin needs (e.g.
    ``("anthropic_key",)``). The factory is the authoritative check."""

    priority: int = 0
    """Sort order for surfaces where priority matters. Higher fires first;
    consumed by :func:`load_surface_sorted`."""


def load_surface(
    surface_path: str,
    protocol: type[T],
    context: object,
    *,
    logger: logging.Logger | None = None,
) -> dict[str, T]:
    """Discover + instantiate every plugin in ``surface_path`` matching ``protocol``.

    ``context`` is the per-surface construction object passed to each factory
    (a settings object, a richer struct composed at the call site). The framework
    treats it opaquely; each plugin file's factory declares the concrete type it
    expects.

    Returns ``{manifest.name: instance}``. Unavailable plugins are logged at DEBUG
    and dropped — they don't appear in the registry. Module-level side effects in
    plugin files break the model (every module gets imported here), so keep plugin
    files declaration-only.

    ``logger`` routes diagnostics onto a caller-supplied logger; when omitted a
    package-local ``plugin_surface`` logger is used.
    """
    log = logger or _DEFAULT_LOGGER
    pkg = importlib.import_module(surface_path)
    registry: dict[str, T] = {}
    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        _try_register(pkg, protocol, context, registry, log)
        return registry

    for module_info in pkgutil.iter_modules(pkg_path, prefix=f"{surface_path}."):
        module = importlib.import_module(module_info.name)
        _try_register(module, protocol, context, registry, log)
    return registry


def _try_register(
    module: object,
    protocol: type[T],
    context: object,
    registry: dict[str, T],
    log: logging.Logger,
) -> None:
    manifest = getattr(module, "MANIFEST", None)
    if manifest is None:
        return  # not a plugin file — utility modules in the surface dir
    if not isinstance(manifest, PluginManifest):
        log.warning(
            "plugin_manifest_wrong_type",
            extra={"fields": {"module": getattr(module, "__name__", "?"), "kind": type(manifest).__name__}},
        )
        return
    if manifest.protocol is not protocol:
        return  # different surface in the same dir — not ours
    instance = manifest.factory(context)
    if isinstance(instance, Unavailable):
        log.debug(
            "plugin_unavailable",
            extra={"fields": {"surface": getattr(module, "__package__", "?"), "name": manifest.name, "reason": instance.reason}},
        )
        return
    registry[manifest.name] = instance


def load_surface_sorted(
    surface_path: str,
    protocol: type[T],
    context: object,
    *,
    logger: logging.Logger | None = None,
) -> list[tuple[str, T]]:
    """Like :func:`load_surface`, ordered by descending ``priority``.

    Returns ``[(name, instance), ...]``. Use for surfaces where dispatch order
    matters.
    """
    log = logger or _DEFAULT_LOGGER
    pkg = importlib.import_module(surface_path)
    items: list[tuple[int, str, T]] = []
    pkg_path = getattr(pkg, "__path__", None)
    modules: list[object]
    if pkg_path is None:
        modules = [pkg]
    else:
        modules = [importlib.import_module(info.name) for info in pkgutil.iter_modules(pkg_path, prefix=f"{surface_path}.")]
    for module in modules:
        manifest = getattr(module, "MANIFEST", None)
        if manifest is None or not isinstance(manifest, PluginManifest):
            continue
        if manifest.protocol is not protocol:
            continue
        instance = manifest.factory(context)
        if isinstance(instance, Unavailable):
            log.debug(
                "plugin_unavailable",
                extra={"fields": {"surface": getattr(module, "__package__", "?"), "name": manifest.name, "reason": instance.reason}},
            )
            continue
        items.append((manifest.priority, manifest.name, instance))
    items.sort(key=lambda kv: -kv[0])
    return [(name, inst) for _prio, name, inst in items]


__all__ = ("PluginManifest", "Unavailable", "load_surface", "load_surface_sorted")
