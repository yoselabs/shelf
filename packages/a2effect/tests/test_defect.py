"""BDD scenarios for typed-error-contract / UnexpectedDefect quarantine."""

import asyncio

import pytest
from a2effect import AppError, UnexpectedDefect
from a2effect.defect import quarantine


def test_unexpected_defect_is_app_error_subclass_with_bug_kind() -> None:
    assert issubclass(UnexpectedDefect, AppError)
    assert UnexpectedDefect.kind == "bug"
    assert UnexpectedDefect.retryable is False


def test_unexpected_defect_envelope_does_not_leak_original_type_at_top_level() -> None:
    original = KeyError("foo")
    defect = quarantine(original)
    env = defect.to_envelope()
    assert env.code == "internal_error"
    assert env.retryable is False
    # The original type stays on the chained cause, server-side; it is not on the wire.
    assert "KeyError" not in env.model_dump_json()
    assert isinstance(defect.__cause__, KeyError)


def test_quarantine_preserves_original_on_cause() -> None:
    original = KeyError("missing")
    defect = quarantine(original)
    assert defect.__cause__ is original


def test_quarantine_wraps_cancelled_error_as_defect() -> None:
    cancelled = asyncio.CancelledError()
    defect = quarantine(cancelled)
    assert defect.to_envelope().code == "internal_error"
    assert isinstance(defect.__cause__, asyncio.CancelledError)


def test_quarantine_wraps_keyboard_interrupt() -> None:
    defect = quarantine(KeyboardInterrupt())
    assert defect.to_envelope().code == "internal_error"
    assert isinstance(defect.__cause__, KeyboardInterrupt)


def test_unexpected_defect_cannot_be_subclassed() -> None:
    with pytest.raises(TypeError, match="final"):

        class _Subclass(UnexpectedDefect):
            pass


def test_quarantine_idempotent_on_app_error() -> None:
    class _NotFoundError(AppError):
        kind = "input"
        code = "not_found"

    original = _NotFoundError("x")
    result = quarantine(original)
    assert result is original
