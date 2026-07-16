"""BDD scenarios for error-contract-tests / contract_tests helper."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

import pytest
from a2effect import AppError
from a2effect.testing import contract_tests


class _NotFoundError(AppError):
    kind = "input"


class _InvalidIdError(AppError):
    kind = "input"


class _InfraError(AppError):
    kind = "infra"
    retryable = True


@dataclass
class _Tool:
    name: str
    raises: tuple[type[AppError], ...]


@dataclass
class _App:
    tools: list[_Tool]
    enrichers: list[Callable[..., AppError | None]] = field(default_factory=list)


def test_contract_tests_generates_envelope_round_trip() -> None:
    app = _App(tools=[_Tool("fetch", (_NotFoundError, _InvalidIdError))])
    tests = contract_tests(app, dead_enricher=False, surface_parity=False)
    assert "test_envelope_round_trip" in tests


def test_contract_tests_envelope_round_trip_passes_for_valid_setup() -> None:
    app = _App(tools=[_Tool("fetch", (_NotFoundError,))])
    tests = contract_tests(app, dead_enricher=False, surface_parity=False)
    # Calling the parametrized test with the case args should pass.
    tests["test_envelope_round_trip"]("fetch", _NotFoundError)  # type: ignore[attr-defined]


def test_contract_tests_disables_dead_enricher_category() -> None:
    app = _App(tools=[_Tool("fetch", (_NotFoundError,))])
    tests = contract_tests(app, dead_enricher=False, surface_parity=False)
    assert "test_dead_enricher" not in tests


def test_contract_tests_dead_enricher_detects_orphan() -> None:
    def orphan_enricher(exc: Exception) -> _InfraError | None:
        return None

    app = _App(
        tools=[_Tool("fetch", (_NotFoundError,))],
        enrichers=[orphan_enricher],
    )
    tests = contract_tests(app, envelope_round_trip=False, surface_parity=False)
    assert "test_dead_enricher" in tests
    with pytest.raises(AssertionError):
        tests["test_dead_enricher"]("orphan_enricher", "_InfraError")  # type: ignore[attr-defined]


def test_contract_tests_dead_enricher_passes_when_all_covered() -> None:
    def covered_enricher(exc: Exception) -> _NotFoundError | None:
        return None

    app = _App(
        tools=[_Tool("fetch", (_NotFoundError,))],
        enrichers=[covered_enricher],
    )
    tests = contract_tests(app, envelope_round_trip=False, surface_parity=False)
    # No-op test should be present and callable without raising
    tests["test_dead_enricher"]()


def test_contract_tests_surface_parity_skipped_when_renderer_absent() -> None:
    app = _App(tools=[_Tool("fetch", (_NotFoundError,))])
    tests = contract_tests(app, envelope_round_trip=False, dead_enricher=False)
    assert "test_surface_parity" not in tests


def test_contract_tests_surface_parity_detects_drift() -> None:
    class _AppWithRenderer:
        tools: ClassVar = [_Tool("fetch", (_NotFoundError,))]
        enrichers: ClassVar[list[Any]] = []

        @staticmethod
        def render_envelope_for(surface: str, exc: AppError) -> dict[str, Any]:
            env = exc.to_envelope_dict()
            if surface == "http":
                env["hint"] = "WRONG"  # introduce surface drift
            return env

    tests = contract_tests(_AppWithRenderer(), envelope_round_trip=False, dead_enricher=False)
    with pytest.raises(AssertionError):
        tests["test_surface_parity"]("fetch", _NotFoundError)  # type: ignore[attr-defined]


def test_contract_tests_surface_parity_passes_when_aligned() -> None:
    class _AppWithRenderer:
        tools: ClassVar = [_Tool("fetch", (_NotFoundError,))]
        enrichers: ClassVar[list[Any]] = []

        @staticmethod
        def render_envelope_for(surface: str, exc: AppError) -> dict[str, Any]:
            return exc.to_envelope_dict()

    tests = contract_tests(_AppWithRenderer(), envelope_round_trip=False, dead_enricher=False)
    tests["test_surface_parity"]("fetch", _NotFoundError)  # type: ignore[attr-defined]
