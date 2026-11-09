"""Strict answer decoding, independent of execution outcome or workflow acceptance."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class DecodedAnswer[T]:
    """One answer accepted by the caller's typed decoder."""

    value: T


@dataclass(frozen=True, slots=True)
class MissingAnswer:
    """No nonwhitespace answer was returned."""


@dataclass(frozen=True, slots=True)
class InvalidAnswer:
    """Malformed JSON or a caller-declared schema validation failure."""

    kind: Literal["json", "schema"]
    reason: str


type Answer[T] = DecodedAnswer[T] | MissingAnswer | InvalidAnswer


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            msg = f"duplicate object key: {key}"
            raise ValueError(msg)
        result[key] = value
    return result


def _finite(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        msg = "nonfinite JSON number"
        raise ValueError(msg)
    return value


def decode_answer[T](text: str, decode: Callable[[object], T]) -> Answer[T]:
    """Decode one complete strict JSON answer; ValueError from decode is schema rejection.

    No extraction, repair or execution occurs. Unexpected decoder faults propagate.
    A valid answer does not imply execution or workflow success.
    """
    if not text.strip():
        return MissingAnswer()
    try:
        value: object = json.loads(text, object_pairs_hook=_pairs, parse_float=_finite, parse_constant=_finite)
    except ValueError as exc:
        return InvalidAnswer(kind="json", reason=str(exc)[:300])
    try:
        return DecodedAnswer(decode(value))
    except ValueError as exc:
        return InvalidAnswer(kind="schema", reason=str(exc)[:300])
