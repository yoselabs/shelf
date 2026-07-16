"""BDD scenarios for typed-error-contract / AppError sealed hierarchy."""

import pytest
from a2effect import AppError, register_error_kind


def test_subclass_with_core_kind_is_created() -> None:
    class NotFoundError(AppError):
        kind = "input"

    err = NotFoundError("x")
    assert err.kind == "input"
    assert err.base_kind == "input"
    assert err.retryable is False
    assert err.hint is None
    assert err.http_status is None
    assert err.cli_exit_code is None


def test_subclass_without_kind_raises_type_error() -> None:
    with pytest.raises(TypeError, match="kind"):

        class BadError(AppError):
            pass


def test_per_instance_override_of_retryable() -> None:
    class InfrastructureError(AppError):
        kind = "infra"
        retryable = True

    err = InfrastructureError("conn refused", retryable=False)
    assert err.retryable is False
    assert InfrastructureError.retryable is True


def test_per_instance_override_of_hint_and_details() -> None:
    class NotFoundError(AppError):
        kind = "input"
        hint = "default hint"

    err = NotFoundError("x", hint="custom hint", details={"id": "abc"})
    assert err.hint == "custom hint"
    assert err.details == {"id": "abc"}


def test_kind_is_not_per_instance_overridable() -> None:
    class NotFoundError(AppError):
        kind = "input"

    err = NotFoundError("x")
    with pytest.raises(TypeError, match="kind"):
        NotFoundError("x", kind="infra")  # ty: ignore[unknown-argument] - deliberately passing an unknown kwarg to assert TypeError
    assert err.kind == "input"


def test_unregistered_extended_kind_raises_at_class_creation() -> None:
    with pytest.raises(TypeError, match="weird"):

        class WeirdError(AppError):
            kind = "weird"


def test_extended_kind_registers_and_resolves_base_kind() -> None:
    register_error_kind("rate_limit", base="infra", retryable=True)

    class RateLimitError(AppError):
        kind = "rate_limit"

    err = RateLimitError("hit")
    assert err.kind == "rate_limit"
    assert err.base_kind == "infra"
    assert err.retryable is True


def test_class_level_metadata_defaults() -> None:
    class AuthFailedError(AppError):
        kind = "auth"

    assert AuthFailedError.retryable is False
    assert AuthFailedError.hint is None
    assert AuthFailedError.http_status is None
    assert AuthFailedError.cli_exit_code is None


def test_class_level_http_status_override() -> None:
    class NotFoundError(AppError):
        kind = "input"
        http_status = 404

    assert NotFoundError("x").http_status == 404


def test_app_error_base_itself_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="kind"):
        AppError("x")
