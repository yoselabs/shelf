"""`UnexpectedDefect` — the terminal wrapper for any unexpected (untyped) exception."""

from __future__ import annotations

from typing import Any

from a2effect.errors import AppError


class UnexpectedDefect(AppError):  # noqa: N818 - deliberate public name (a "defect", not an "…Error")
    """A bug-kind error wrapping an exception that was never typed.

    Final — it must not be subclassed; a typed defect subclasses :class:`AppError`
    with ``kind="bug"`` instead. Produced by :func:`quarantine`.
    """

    kind = "bug"
    retryable = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        msg = (
            f"UnexpectedDefect is final and SHALL NOT be subclassed; got {cls.__name__!r}. "
            f"To carry a typed defect, subclass AppError directly with kind='bug'."
        )
        raise TypeError(msg)


def quarantine(exc: BaseException) -> AppError:
    """Return `exc` if it is already an :class:`AppError`, else wrap it as a defect."""
    if isinstance(exc, AppError):
        return exc
    wrapped = UnexpectedDefect(str(exc) or type(exc).__name__)
    wrapped.__cause__ = exc
    return wrapped
