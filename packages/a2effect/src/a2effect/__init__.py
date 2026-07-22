"""a2effect — a standalone, pydantic-only typed-error foundation.

Public API: :class:`AppError` (+ its `kind` taxonomy and wire :class:`ErrorEnvelope`),
:class:`UnexpectedDefect` for quarantining untyped exceptions, the :class:`Raises`
return marker, and the `raises_as`/`translate_to` boundary translators.
"""

from a2effect.defect import UnexpectedDefect
from a2effect.envelope import ErrorEnvelope
from a2effect.errors import AppError, ErrorKind, register_error_kind
from a2effect.raises import Raises
from a2effect.translate import raises_as, translate_to

__all__ = [
    "AppError",
    "ErrorEnvelope",
    "ErrorKind",
    "Raises",
    "UnexpectedDefect",
    "raises_as",
    "register_error_kind",
    "translate_to",
]
