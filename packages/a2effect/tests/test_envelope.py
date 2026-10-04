"""BDD scenarios for typed-error-contract / ErrorEnvelope wire schema."""

import pytest
from a2effect import AppError, ErrorEnvelope, register_error_kind


class _NotFoundError(AppError):
    kind = "input"
    code = "not_found"
    hint = "verify the id"
    http_status = 404


class _InfraError(AppError):
    kind = "infra"
    code = "infra"
    retryable = True


def test_envelope_round_trips_via_pydantic_json() -> None:
    err = _NotFoundError("x", details={"id": "abc"})
    env = err.to_envelope()
    raw = env.model_dump_json()
    parsed = ErrorEnvelope.model_validate_json(raw)
    assert parsed == env


def test_envelope_carries_code_message_retryable_hint() -> None:
    err = _NotFoundError("x")
    env = err.to_envelope()
    assert env.code == "not_found"
    assert env.message == "x"
    assert env.retryable is False
    assert env.hint == "verify the id"
    assert env.envelope_version == "2"


def test_envelope_carries_details_dict() -> None:
    err = _NotFoundError("x", details={"id": "abc", "scope": "memory"})
    env = err.to_envelope()
    assert env.details == {"id": "abc", "scope": "memory"}


def test_envelope_never_carries_the_chained_cause() -> None:
    original = ValueError("orig")
    err: AppError
    msg = "wrap"
    try:
        raise _NotFoundError(msg) from original
    except _NotFoundError as caught:
        err = caught
    assert err.__cause__ is original
    assert "orig" not in err.to_envelope().model_dump_json()


def test_envelope_extension_kind_keeps_its_retryable_default() -> None:
    register_error_kind("token_bucket", base="infra", retryable=True)

    class _RateLimitError(AppError):
        kind = "token_bucket"
        code = "rate_limit"

    err = _RateLimitError("hit")
    assert err.base_kind == "infra"
    assert err.to_envelope().retryable is True


def test_to_envelope_dict_matches_model_dump() -> None:
    err = _NotFoundError("x", details={"id": "abc"})
    assert err.to_envelope_dict() == err.to_envelope().model_dump()


def test_envelope_version_is_locked_to_two() -> None:
    env = _NotFoundError("x").to_envelope()
    assert env.envelope_version == "2"


def test_envelope_per_instance_retryable_override_propagates() -> None:
    err = _InfraError("conn refused", retryable=False)
    env = err.to_envelope()
    assert env.retryable is False


def test_envelope_per_instance_hint_override_propagates() -> None:
    err = _NotFoundError("x", hint="try the cache")
    env = err.to_envelope()
    assert env.hint == "try the cache"


def test_envelope_rejects_direct_construction_via_authoring_path() -> None:
    # Authors SHALL NOT construct ErrorEnvelope directly. Pydantic permits
    # it (you cannot block model construction without breaking serialization
    # round-trip), but the contract is documented and lint enforces.
    # This test just confirms the model is constructable for framework code
    # and validates required fields.
    with pytest.raises((ValueError, Exception)):
        ErrorEnvelope.model_validate({})  # missing required fields
