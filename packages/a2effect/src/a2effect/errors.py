"""The typed-error base (`AppError`) and the kind taxonomy.

Every error a framework puts on the wire subclasses :class:`AppError` and declares a
`kind` — one of the five core kinds, or an extension registered via
:func:`register_error_kind`. The kind drives the wire envelope, HTTP status, and CLI
exit code, so a consumer maps error categories once, not per exception type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from a2effect.envelope import ErrorEnvelope, _extract_cause

ErrorKind = Literal["input", "auth", "policy", "infra", "bug"]

_CORE_KINDS: frozenset[str] = frozenset({"input", "auth", "policy", "infra", "bug"})


@dataclass(frozen=True, slots=True)
class _Extension:
    name: str
    base: ErrorKind
    retryable: bool


_KIND_EXTENSIONS: dict[str, _Extension] = {}


def register_error_kind(name: str, *, base: ErrorKind, retryable: bool = False) -> None:
    """Register a domain error kind that resolves to a core `base` kind.

    Lets a framework name its own categories (e.g. ``"rate_limit"`` based on
    ``"infra"``) while the wire/HTTP/CLI mapping keeps working off the base kind.
    """
    if name in _CORE_KINDS:
        msg = f"cannot redefine core kind {name!r}"
        raise ValueError(msg)
    if base not in _CORE_KINDS:
        msg = f"extension base must be a core kind, got {base!r}; accepted: {sorted(_CORE_KINDS)}"
        raise ValueError(msg)
    _KIND_EXTENSIONS[name] = _Extension(name=name, base=base, retryable=retryable)


def _resolve_base_kind(kind: str) -> str:
    if kind in _CORE_KINDS:
        return kind
    ext = _KIND_EXTENSIONS.get(kind)
    if ext is None:
        msg = (
            f"unknown kind {kind!r}; accepted core kinds: {sorted(_CORE_KINDS)}; "
            f"register extensions via a2effect.register_error_kind(name, base=...)"
        )
        raise TypeError(msg)
    return ext.base


def _extension_default_retryable(kind: str) -> bool | None:
    ext = _KIND_EXTENSIONS.get(kind)
    return ext.retryable if ext is not None else None


class AppError(Exception):
    """Base for every typed, wire-serializable application error.

    A subclass MUST declare a class-level `kind`; the base resolves it to a core
    `base_kind` and exposes the wire envelope (:meth:`to_envelope`), HTTP status, and
    CLI exit code. Instances carry a message, optional `hint`/`details`, and a `cause`.
    """

    kind: ClassVar[str]
    retryable: ClassVar[bool] = False
    hint: ClassVar[str | None] = None
    http_status: ClassVar[int | None] = None
    cli_exit_code: ClassVar[int | None] = None
    #: Overrides the default kind label in error prose (e.g.,
    #: ``"Authorization denied"`` for an auth-kind subclass that wants
    #: distinct framing from the default ``"Authentication required"``).
    kind_label: ClassVar[str | None] = None

    base_kind: str
    details: dict[str, Any]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "kind" not in cls.__dict__:
            msg = (
                f"AppError subclass {cls.__name__!r} must declare a class-level `kind` attribute "
                f"(one of {sorted(_CORE_KINDS)} or a registered extension)"
            )
            raise TypeError(msg)
        kind = cls.__dict__["kind"]
        if kind not in _CORE_KINDS and kind not in _KIND_EXTENSIONS:
            msg = (
                f"AppError subclass {cls.__name__!r} declares unknown kind {kind!r}; "
                f"accepted core kinds: {sorted(_CORE_KINDS)}; "
                f"register extensions via a2effect.register_error_kind(name, base=...)"
            )
            raise TypeError(msg)
        if kind not in _CORE_KINDS and "retryable" not in cls.__dict__:
            ext_default = _extension_default_retryable(kind)
            if ext_default is not None:
                cls.retryable = ext_default

    def __init__(
        self,
        msg: str = "",
        *,
        retryable: bool | None = None,
        hint: str | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if type(self) is AppError or "kind" not in type(self).__dict__:
            msg = (
                "cannot instantiate AppError directly; subclass and declare `kind`"
                if type(self) is AppError
                else f"{type(self).__name__} missing class-level `kind`"
            )
            raise TypeError(msg)
        super().__init__(msg)
        self.base_kind = _resolve_base_kind(type(self).kind)
        if retryable is not None:
            self.retryable = retryable  # ty: ignore[invalid-attribute-access] - deliberate per-instance override of the class default
        if hint is not None:
            self.hint = hint  # ty: ignore[invalid-attribute-access] - deliberate per-instance override of the class default
        self.details = details if details is not None else {}
        if cause is not None:
            self.__cause__ = cause

    def to_envelope(self) -> ErrorEnvelope:
        """Render this error as its structured wire :class:`ErrorEnvelope`."""
        return ErrorEnvelope(
            type=type(self).__name__,
            kind=type(self).kind,
            base_kind=self.base_kind,
            retryable=self.retryable,
            hint=self.hint,
            details=self.details,
            cause=_extract_cause(self),
        )

    def to_envelope_dict(self) -> dict[str, Any]:
        """The wire envelope as a plain ``dict`` (``model_dump`` of :meth:`to_envelope`)."""
        return self.to_envelope().model_dump()


class InputError(AppError):
    """Caller supplied something malformed or missing (HTTP 400 / exit 2)."""

    kind = "input"
    http_status = 400
    cli_exit_code = 2


class AuthError(AppError):
    """Authentication is required or failed (HTTP 401 / exit 77)."""

    kind = "auth"
    http_status = 401
    cli_exit_code = 77


class PolicyError(AppError):
    """A rule (scope, cardinality, retention) said no (HTTP 403 / exit 77)."""

    kind = "policy"
    http_status = 403
    cli_exit_code = 77


class InfrastructureError(AppError):
    """An IO / engine / external-service failure — retryable (HTTP 503 / exit 75)."""

    kind = "infra"
    retryable = True
    http_status = 503
    cli_exit_code = 75
