"""The typed-error base (`AppError`), the kind taxonomy and the error `code`.

Every error a framework puts on the wire subclasses :class:`AppError` and declares a
`kind` — one of the five core kinds, or an extension registered via
:func:`register_error_kind` — and a `code`, the snake_case name of what went wrong. The
kind drives HTTP status and CLI exit code, so a consumer maps error categories once, not
per exception type; the code is what a caller branches on. An intermediate base declares
itself ``abstract=True`` and may omit both; it cannot be raised.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from a2effect.envelope import ErrorEnvelope

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


_CODE = re.compile(r"^[a-z][a-z0-9_]*$")


class AppError(Exception):
    """Base for every typed, wire-serializable application error.

    A concrete subclass MUST declare a class-level `kind` and `code` in its own body (an
    inherited code would let two classes share one); the base resolves the kind to a core
    `base_kind` and exposes the wire envelope (:meth:`to_envelope`), HTTP status, and CLI
    exit code. Instances carry a message, optional `hint`/`details`, and a `cause` that
    stays server-side. ``class Base(AppError, abstract=True)`` declares an intermediate
    base that may omit both and cannot be instantiated.
    """

    kind: ClassVar[str]
    code: ClassVar[str]
    retryable: ClassVar[bool] = False
    hint: ClassVar[str | None] = None
    http_status: ClassVar[int | None] = None
    cli_exit_code: ClassVar[int | None] = None
    #: Overrides the default kind label in error prose (e.g.,
    #: ``"Authorization denied"`` for an auth-kind subclass that wants
    #: distinct framing from the default ``"Authentication required"``).
    kind_label: ClassVar[str | None] = None
    #: Set on every subclass from its ``abstract=`` class keyword; read by :meth:`is_abstract`.
    _abstract: ClassVar[bool] = True

    base_kind: str
    details: dict[str, Any]

    def __init_subclass__(cls, *, abstract: bool = False, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._abstract = abstract
        own = cls.__dict__
        if "kind" not in own and not abstract:
            msg = (
                f"AppError subclass {cls.__name__!r} must declare a class-level `kind` attribute "
                f"(one of {sorted(_CORE_KINDS)} or a registered extension)"
            )
            raise TypeError(msg)
        if "kind" in own:
            kind = own["kind"]
            if kind not in _CORE_KINDS and kind not in _KIND_EXTENSIONS:
                msg = (
                    f"AppError subclass {cls.__name__!r} declares unknown kind {kind!r}; "
                    f"accepted core kinds: {sorted(_CORE_KINDS)}; "
                    f"register extensions via a2effect.register_error_kind(name, base=...)"
                )
                raise TypeError(msg)
            if kind not in _CORE_KINDS and "retryable" not in own:
                ext_default = _extension_default_retryable(kind)
                if ext_default is not None:
                    cls.retryable = ext_default
        if "code" not in own and not abstract:
            msg = (
                f"AppError subclass {cls.__name__!r} must declare a class-level `code` "
                f"(snake_case, what went wrong), or be declared abstract=True"
            )
            raise TypeError(msg)
        if "code" in own and not (isinstance(own["code"], str) and _CODE.match(own["code"])):
            msg = f"AppError subclass {cls.__name__!r} declares code {own['code']!r}; a code is snake_case ({_CODE.pattern})"
            raise TypeError(msg)

    @classmethod
    def is_abstract(cls) -> bool:
        """True for an intermediate base declared ``abstract=True`` (and for `AppError`)."""
        return cls is AppError or cls.__dict__.get("_abstract", False)

    def __init__(
        self,
        msg: str = "",
        *,
        retryable: bool | None = None,
        hint: str | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if type(self).is_abstract():
            msg = (
                "cannot instantiate AppError directly; subclass and declare `kind` and `code`"
                if type(self) is AppError
                else f"{type(self).__name__} is abstract; raise a concrete subclass"
            )
            raise TypeError(msg)
        super().__init__(msg)
        self.base_kind = _resolve_base_kind(type(self).kind)
        if retryable is not None:
            self.retryable = retryable
        if hint is not None:
            self.hint = hint
        self.details = details if details is not None else {}
        if cause is not None:
            self.__cause__ = cause

    def to_envelope(self) -> ErrorEnvelope:
        """Render this error as its structured wire :class:`ErrorEnvelope` (v2)."""
        return ErrorEnvelope(
            code=type(self).code,
            message=str(self),
            hint=self.hint,
            retryable=self.retryable,
            details=self.details,
        )

    def to_envelope_dict(self) -> dict[str, Any]:
        """The wire envelope as a plain ``dict`` (``model_dump`` of :meth:`to_envelope`)."""
        return self.to_envelope().model_dump()


class InputError(AppError, abstract=True):
    """Caller supplied something malformed or missing (HTTP 400 / exit 2)."""

    kind = "input"
    http_status = 400
    cli_exit_code = 2


class AuthError(AppError, abstract=True):
    """Authentication is required or failed (HTTP 401 / exit 77)."""

    kind = "auth"
    http_status = 401
    cli_exit_code = 77


class PolicyError(AppError, abstract=True):
    """A rule (scope, cardinality, retention) said no (HTTP 403 / exit 77)."""

    kind = "policy"
    http_status = 403
    cli_exit_code = 77


class InfrastructureError(AppError, abstract=True):
    """An IO / engine / external-service failure — retryable (HTTP 503 / exit 75)."""

    kind = "infra"
    retryable = True
    http_status = 503
    cli_exit_code = 75


def codes(root: type[AppError]) -> dict[str, type[AppError]]:
    """Every concrete error class under ``root`` (``root`` included), by its code.

    Abstract bases are skipped. Two classes sharing a code is a catalogue defect and
    raises :class:`ValueError` naming both — this is how a consumer's catalogue test and a
    rehydrating client look a code up.
    """
    found: dict[str, type[AppError]] = {}
    seen: set[type[AppError]] = set()
    stack: list[type[AppError]] = [root]
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        stack.extend(cls.__subclasses__())
        if cls.is_abstract():
            continue
        other = found.get(cls.code)
        if other is not None:
            msg = f"code {cls.code!r} is declared by both {other.__name__} and {cls.__name__}"
            raise ValueError(msg)
        found[cls.code] = cls
    return found
