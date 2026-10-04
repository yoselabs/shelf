"""a2effect — a standalone, pydantic-only typed-error foundation.

Public API: :class:`AppError` (+ its `kind` taxonomy, its `code`, the wire
:class:`ErrorEnvelope` and :func:`codes`, which lists a hierarchy's codes),
:class:`UnexpectedDefect` for quarantining untyped exceptions, the :class:`Raises`
return marker, and the `raises_as`/`translate_to` boundary translators.
"""

from a2effect.defect import UnexpectedDefect
from a2effect.envelope import ErrorEnvelope
from a2effect.errors import AppError, ErrorKind, codes, register_error_kind
from a2effect.raises import Raises
from a2effect.translate import raises_as, translate_to

__all__ = [
    "AppError",
    "ErrorEnvelope",
    "ErrorKind",
    "Raises",
    "UnexpectedDefect",
    "codes",
    "raises_as",
    "register_error_kind",
    "translate_to",
]
