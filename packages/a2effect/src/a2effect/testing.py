"""contract_tests(app) — pytest-collectible test generator for the typed-error contract.

The contract checks operate against a minimal `App`-shaped protocol:

  - app.tools: iterable of objects exposing `.name: str` and `.raises: tuple[type[AppError], ...]`.
  - app.enrichers: iterable of callables annotated with a return type
    (`AppError | None` or subclass union).

Surface-parity checking additionally requires `app.render_envelope_for(surface, exc) -> dict`
to be available on the app; if missing, surface-parity tests are skipped, never failed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, get_args, get_type_hints, runtime_checkable

import pytest

from a2effect.errors import AppError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


@runtime_checkable
class _ToolLike(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def raises(self) -> tuple[type[AppError], ...]: ...


@runtime_checkable
class _AppLike(Protocol):
    # Read-only members: `contract_tests` only reads these, so covariant matching lets
    # a concrete `list[Tool]` satisfy `Iterable[_ToolLike]` (a mutable attr would not).
    @property
    def tools(self) -> Iterable[_ToolLike]: ...
    @property
    def enrichers(self) -> Iterable[Callable[..., AppError | None]]: ...


def _enricher_output_types(enricher: Callable[..., AppError | None]) -> set[type[AppError]]:
    try:
        hints = get_type_hints(enricher)
    except Exception:  # noqa: BLE001
        return set()
    rt = hints.get("return")
    if rt is None:
        return set()
    args = get_args(rt)
    candidates = [rt, *args]
    return {c for c in candidates if isinstance(c, type) and issubclass(c, AppError)}


def contract_tests(  # noqa: C901 — three independent check categories share one builder
    app: _AppLike,
    *,
    envelope_round_trip: bool = True,
    dead_enricher: bool = True,
    surface_parity: bool = True,
) -> dict[str, Callable[..., None]]:
    """Generate contract-test callables for an app; call at module scope.

    from a2effect.testing import contract_tests
    from myapp import app

    globals().update(contract_tests(app))
    """
    tools = list(app.tools)
    enrichers = list(getattr(app, "enrichers", ()))
    tests: dict[str, Callable[..., None]] = {}

    if envelope_round_trip:
        cases = [(tool.name, exc_type) for tool in tools for exc_type in tool.raises]
        if cases:

            @pytest.mark.parametrize(
                ("tool_name", "exc_type"),
                cases,
                ids=[f"{name}-{t.__name__}" for name, t in cases],
            )
            def test_envelope_round_trip(tool_name: str, exc_type: type[AppError]) -> None:
                instance = exc_type("sample")
                env = instance.to_envelope()
                assert env.type == exc_type.__name__, f"{tool_name}: type {env.type!r} != {exc_type.__name__!r}"  # noqa: S101
                assert env.kind == exc_type.kind, f"{tool_name}: kind {env.kind!r} != {exc_type.kind!r}"  # noqa: S101
                assert env.retryable == exc_type.retryable  # noqa: S101

            tests["test_envelope_round_trip"] = test_envelope_round_trip

    if dead_enricher and enrichers:
        all_declared: set[type[AppError]] = {t for tool in tools for t in tool.raises}
        dead: list[tuple[Callable[..., AppError | None], type[AppError]]] = []
        for enricher in enrichers:
            outputs = _enricher_output_types(enricher)
            for out in outputs:
                if out is AppError:
                    continue
                if not any(issubclass(out, declared) or issubclass(declared, out) for declared in all_declared):
                    dead.append((enricher, out))
        if dead:
            params = [(getattr(e, "__qualname__", repr(e)), t.__name__) for e, t in dead]

            @pytest.mark.parametrize(
                ("enricher_name", "output_type"),
                params,
                ids=[f"{name}-{otype}" for name, otype in params],
            )
            def test_dead_enricher(enricher_name: str, output_type: str) -> None:
                msg = f"enricher {enricher_name} outputs {output_type} but no tool declares it in Raises(...)"
                raise AssertionError(msg)

            tests["test_dead_enricher"] = test_dead_enricher
        else:

            def test_dead_enricher() -> None:
                pass

            tests["test_dead_enricher"] = test_dead_enricher

    if surface_parity and hasattr(app, "render_envelope_for"):
        renderer: Callable[[str, AppError], dict[str, Any]] = getattr(app, "render_envelope_for")  # noqa: B009 - dynamic optional protocol member
        cases = [(tool.name, exc_type) for tool in tools for exc_type in tool.raises]
        if cases:

            @pytest.mark.parametrize(
                ("tool_name", "exc_type"),
                cases,
                ids=[f"{name}-{t.__name__}" for name, t in cases],
            )
            def test_surface_parity(tool_name: str, exc_type: type[AppError]) -> None:
                instance = exc_type("sample")
                surfaces = ("mcp", "http", "cli")
                rendered = {s: renderer(s, instance) for s in surfaces}
                ref_keys = ("type", "kind", "retryable", "hint")
                ref = {k: rendered["mcp"].get(k) for k in ref_keys}
                for s in surfaces[1:]:
                    actual = {k: rendered[s].get(k) for k in ref_keys}
                    assert actual == ref, f"{tool_name} surface {s!r} drifted from mcp: {actual} != {ref}"  # noqa: S101

            tests["test_surface_parity"] = test_surface_parity

    return tests
