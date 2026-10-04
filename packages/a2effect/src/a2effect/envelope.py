"""`ErrorEnvelope` — the versioned, machine-readable wire shape of a typed error."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ENVELOPE_VERSION: Literal["2"] = "2"


class ErrorEnvelope(BaseModel):
    """The serialized form of an :class:`~a2effect.errors.AppError` on the wire (v2).

    `code` says what went wrong, `message` is the sentence, `hint` what to do next (or
    null), `retryable` whether the same call can succeed unchanged or after a re-read, and
    `details` the facts to act on. The class name, the effect kind and the chained cause
    are not on the wire: the kind picks HTTP status and exit code, the cause is the
    server's to log.
    """

    code: str
    message: str
    hint: str | None = None
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)
    envelope_version: Literal["2"] = ENVELOPE_VERSION
