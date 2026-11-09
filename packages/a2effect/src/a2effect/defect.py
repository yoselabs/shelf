"""`UnexpectedDefect` — the terminal wrapper for any unexpected (untyped) exception."""

from __future__ import annotations

from typing import Any, final

from a2effect.errors import AppError


class _DefectType(type):
    def __new__(
        mcls: type[_DefectType], name: str, bases: tuple[type[object], ...], namespace: dict[str, object], /, **kwargs: Any
    ) -> _DefectType:
        if any(isinstance(base, _DefectType) for base in bases):
            msg = (
                f"UnexpectedDefect is final and SHALL NOT be subclassed; got {name!r}. "
                "To carry a typed defect, subclass AppError directly with kind='bug'."
            )
            raise TypeError(msg)
        return super().__new__(mcls, name, bases, namespace, **kwargs)


@final
class UnexpectedDefect(AppError, metaclass=_DefectType):  # noqa: N818 - deliberate public name (a "defect", not an "…Error")
    """A bug-kind error wrapping an exception that was never typed.

    Final — it must not be subclassed; a typed defect subclasses :class:`AppError`
    with ``kind="bug"`` instead. Produced by :func:`quarantine`.
    """

    kind = "bug"
    code = "internal_error"
    retryable = False


def quarantine(exc: BaseException) -> AppError:
    """Return `exc` if it is already an :class:`AppError`, else wrap it as a defect."""
    if isinstance(exc, AppError):
        return exc
    wrapped = UnexpectedDefect(str(exc) or type(exc).__name__)
    wrapped.__cause__ = exc
    return wrapped
