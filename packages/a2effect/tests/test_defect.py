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


@pytest.mark.parametrize("attributes", [{}, {"kind": "unknown"}, {"code": "INVALID"}])
@pytest.mark.parametrize(
    "keywords",
    [
        {},
        {"abstract": True},
        {"abstract": False},
        {"unknown": True},
        {"name": "value"},
        {"bases": "value"},
        {"namespace": "value"},
        {"mcls": "value"},
    ],
)
def test_unexpected_defect_cannot_be_subclassed(attributes: dict[str, object], keywords: dict[str, object]) -> None:
    before = dict(UnexpectedDefect.__dict__)
    with pytest.raises(TypeError, match="UnexpectedDefect is final") as caught:
        type("_Subclass", (UnexpectedDefect,), attributes, **keywords)
    assert str(caught.value) == (
        "UnexpectedDefect is final and SHALL NOT be subclassed; got '_Subclass'. "
        "To carry a typed defect, subclass AppError directly with kind='bug'."
    )
    assert dict(UnexpectedDefect.__dict__) == before


def test_quarantine_idempotent_on_app_error() -> None:
    class _NotFoundError(AppError):
        kind = "input"
        code = "not_found"

    original = _NotFoundError("x")
    result = quarantine(original)
    assert result is original


@pytest.mark.parametrize("mixin_first", [False, True])
def test_final_defect_rejection_does_not_execute_a_mixin_hook(mixin_first: bool) -> None:
    calls: list[str] = []

    class Mixin:
        def __init_subclass__(cls, **kwargs: object) -> None:
            calls.append(cls.__name__)
            msg = "mixin hook must not run for a final defect"
            raise RuntimeError(msg)

    with pytest.raises(TypeError, match="UnexpectedDefect is final"):
        bases = (Mixin, UnexpectedDefect) if mixin_first else (UnexpectedDefect, Mixin)
        type("Child", bases, {})
    assert calls == []
