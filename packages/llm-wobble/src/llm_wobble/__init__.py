"""LLM-contract-parsing discipline — the typed funnel.

An LLM asked for JSON returns it fenced, prose-wrapped, or with fields dropped.
Every site that consumes such output SHOULD funnel through `parse_with_policy`
(object envelopes) or `parse_list_with_policy` (array envelopes). The funnel:

  1. Strips ```` ```json ```` fences (and recovers the first balanced object
     when the model trails prose or a second fence after it).
  2. Calls `json.loads` — the single decode site a consumer can then ban
     everywhere else, so no hand-rolled parse can bypass the policy.
  3. Applies a per-field `WobblePolicy` (STRICT raises, DERIVE/DEFAULT/SKIP
     recover, each recovery firing one structured `llm_wobble` log event).
  4. Constructs the typed payload and wraps it in `Wobbled`.

`Wobbled` is an opaque `NewType` whose only constructor is the funnel — code
typed as `Wobbled` cannot accept a dict fabricated outside it, so the bypass is
a deliberate type-ignore, not an accident.

**Logging is injected, never named for a consumer.** Recoveries emit on the
`llm_wobble` logger by default; pass `logger=` to route them onto a host's own
managed channel (e.g. an app that keeps a single process logger). The record
shape is `message="llm_wobble"` + a `fields` payload on `record.fields`, so any
handler drains it uniformly.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Generic, NewType, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

_DEFAULT_LOGGER = logging.getLogger("llm_wobble")

_RAW_EXCERPT_MAX = 200

T = TypeVar("T")


class WobbleTolerance(StrEnum):
    """Per-field policy for what to do when an LLM drops a JSON field."""

    STRICT = "strict"
    DERIVE = "derive"
    DEFAULT = "default"
    SKIP = "skip"


@dataclass(slots=True, frozen=True)
class WobblePolicy:
    """One field's wobble-tolerance policy.

    `default` is meaningful only when `tolerance == DEFAULT`.
    `derive` is meaningful only when `tolerance == DERIVE`.
    """

    tolerance: WobbleTolerance
    default: Any = None
    derive: Callable[[dict[str, Any]], Any] | None = None


class WobbleSkip(Exception):  # noqa: N818 - control-flow signal, not an error; public API name
    """Raised when a SKIP-policy field is missing — caller short-circuits."""


class ParseError(Exception):
    """Raise when an envelope cannot be honoured.

    The raw text failed JSON decode, isn't a dict/list, or violates a STRICT
    policy. Callers translate to their boundary-specific error type.
    """


@dataclass(frozen=True, slots=True)
class _Parsed(Generic[T]):
    """Private payload — constructed only inside this module."""

    value: T
    recovered_fields: tuple[str, ...]


Wobbled = NewType("Wobbled", _Parsed[Any])


def unwrap(w: Wobbled) -> Any:
    """Extract the wrapped value. Caller's local annotation narrows the type."""
    return w.value  # type: ignore[attr-defined]


def recovered_fields(w: Wobbled) -> tuple[str, ...]:
    """Names of fields that fell back to DERIVE/DEFAULT/SKIP recovery."""
    return w.recovered_fields  # type: ignore[attr-defined]


def _strip_fences(text: str) -> str:
    """Strip optional ```...``` (or ```json...```) markdown fences."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped.removeprefix("```").removeprefix("json")
    if "```" in body:
        body = body.split("```", 1)[0]
    return body.strip()


_FENCED_BLOCK_RE = re.compile(r"```[a-zA-Z0-9_-]*[ \t]*\n(?P<body>.*?)\n[ \t]*```", re.DOTALL)


def strip_fenced_blocks(text: str, *, json_only: bool = True) -> str:
    """Remove fenced blocks from prose, keeping the prose.

    The INVERSE of what the parse funnel does. `parse_with_policy` keeps the JSON
    and discards the prose around it; this keeps the prose and discards the JSON.
    Both need to know what a fence looks like, which is why fence syntax lives
    here rather than being re-derived by every caller.

    Use it when a model was asked for prose and emitted an output-contract
    artifact alongside it — a `next_links` array, a stray `json` block — and that
    artifact must not reach a prose-typed field. A fenced block in a field callers
    parse as text inflates tokens, breaks rendering, and puts structured data in a
    channel not reserved for it.

    `json_only=True` (default) drops only blocks whose body opens as JSON
    (`[` or `{`), so genuine code samples in an answer survive. It is a SHAPE
    check, not a parse: the payload is being discarded, so whether it is
    well-formed is irrelevant — a malformed array is exactly as unwelcome in
    prose as a valid one, and requiring validity would silently keep the broken
    ones. `json_only=False` drops every fenced block regardless of content.

    Returns the text with matched blocks removed and surrounding whitespace
    collapsed at the ends. Text with no fences is returned stripped, unchanged.
    """

    def _replace(match: re.Match[str]) -> str:
        if not json_only:
            return ""
        body = match.group("body").strip()
        return "" if body[:1] in ("[", "{") else match.group(0)

    return _FENCED_BLOCK_RE.sub(_replace, text).strip()


def _first_json_object(text: str) -> str | None:
    """Return the first balanced top-level ``{...}`` object substring, or None.

    Recovery path for model outputs that carry the object but do not have it as
    the *whole* payload — e.g. a trailing fence after the object, or prose after
    the JSON. Scanning for the first balanced object lets the funnel parse the
    envelope instead of falling back to raw text. String- and escape-aware so
    braces inside string values do not fool the depth counter.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def emit_wobble(
    *,
    boundary: str,
    field: str,
    tolerance: WobbleTolerance,
    model: str,
    raw_excerpt: str,
    logger: logging.Logger | None = None,
) -> None:
    """Single structured log event for every recovered LLM-contract wobble."""
    (logger or _DEFAULT_LOGGER).warning(
        "llm_wobble",
        extra={
            "fields": {
                "boundary": boundary,
                "field": field,
                "tolerance": tolerance.value,
                "model": model,
                "raw": raw_excerpt[:_RAW_EXCERPT_MAX] if raw_excerpt else "",
            }
        },
    )


def _apply_field(
    parsed: dict[str, Any],
    field: str,
    policy: WobblePolicy,
    *,
    boundary: str,
    model: str,
    raw_excerpt: str,
    logger: logging.Logger | None,
) -> tuple[Any, bool]:
    """Resolve `parsed[field]` against `policy`.

    Returns `(value, recovered)`. `recovered=True` iff a wobble was emitted.
    Raises `KeyError` for STRICT/mis-declared-DERIVE misses, `WobbleSkip` for SKIP.
    """
    present = field in parsed and parsed[field] is not None
    if present:
        return parsed[field], False

    if policy.tolerance is WobbleTolerance.STRICT:
        raise KeyError(field)
    if policy.tolerance is WobbleTolerance.DERIVE:
        if policy.derive is None:
            raise KeyError(field)
        value = policy.derive(parsed)
        emit_wobble(boundary=boundary, field=field, tolerance=policy.tolerance, model=model, raw_excerpt=raw_excerpt, logger=logger)
        return value, True
    if policy.tolerance is WobbleTolerance.DEFAULT:
        emit_wobble(boundary=boundary, field=field, tolerance=policy.tolerance, model=model, raw_excerpt=raw_excerpt, logger=logger)
        return policy.default, True
    if policy.tolerance is WobbleTolerance.SKIP:
        emit_wobble(boundary=boundary, field=field, tolerance=policy.tolerance, model=model, raw_excerpt=raw_excerpt, logger=logger)
        raise WobbleSkip(field)
    msg = f"unknown wobble tolerance: {policy.tolerance}"
    raise RuntimeError(msg)


def parse_with_policy(
    raw: str,
    *,
    policies: Mapping[str, WobblePolicy],
    into: Callable[[dict[str, Any]], T],
    boundary: str,
    model: str,
    logger: logging.Logger | None = None,
) -> Wobbled:
    """Strip fences → `json.loads` → apply per-field policy → `into(resolved_dict)`.

    The only legitimate constructor of `Wobbled` for object envelopes.
    Raises `ParseError` on malformed JSON / wrong root type / STRICT miss.
    `WobbleSkip` propagates so callers can short-circuit.
    """
    stripped = _strip_fences(raw)
    try:
        parsed = json.loads(stripped)
    except (ValueError, json.JSONDecodeError) as exc:
        # Recovery: the object may be present but not the whole payload (trailing
        # fence or prose after it). Extract the first balanced object and retry,
        # firing an `llm_wobble` so the recovery is visible.
        obj = _first_json_object(stripped)
        if obj is None:
            msg = f"{boundary}: invalid JSON: {exc}"
            raise ParseError(msg) from exc
        try:
            parsed = json.loads(obj)
        except (ValueError, json.JSONDecodeError) as exc2:
            msg = f"{boundary}: invalid JSON: {exc2}"
            raise ParseError(msg) from exc2
        emit_wobble(boundary=boundary, field="_envelope", tolerance=WobbleTolerance.DERIVE, model=model, raw_excerpt=raw, logger=logger)
    if not isinstance(parsed, dict):
        msg = f"{boundary}: expected JSON object, got {type(parsed).__name__}"
        raise ParseError(msg)

    resolved: dict[str, Any] = {}
    recovered: list[str] = []
    for field, policy in policies.items():
        try:
            value, was_recovered = _apply_field(parsed, field, policy, boundary=boundary, model=model, raw_excerpt=raw, logger=logger)
        except KeyError as exc:
            msg = f"{boundary}: missing required field: {exc}"
            raise ParseError(msg) from exc
        resolved[field] = value
        if was_recovered:
            recovered.append(field)

    # Surface any non-policied fields too — callers may want them for raw inspection.
    for k, v in parsed.items():
        resolved.setdefault(k, v)

    value_out = into(resolved)
    return Wobbled(_Parsed(value=value_out, recovered_fields=tuple(recovered)))


def parse_list_with_policy(
    raw: str,
    *,
    item: Callable[[dict[str, Any]], T | None],
    boundary: str,
    model: str,
    strip_fences: bool = True,
    logger: logging.Logger | None = None,
) -> Wobbled:
    """Strip fences (optional) → `json.loads` → expect list → filter via `item(...)`.

    For envelopes where the model returns a JSON array. `item(dict) -> T | None`
    returns None to drop malformed entries; that filtering happens inside the
    funnel, not in caller code.

    Returns a `Wobbled` wrapping `list[T]`. `recovered_fields` lists the indices
    (as strings) of dropped entries.
    """
    payload = _strip_fences(raw) if strip_fences else raw.strip()
    try:
        parsed = json.loads(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        msg = f"{boundary}: invalid JSON: {exc}"
        raise ParseError(msg) from exc
    if not isinstance(parsed, list):
        msg = f"{boundary}: expected JSON array, got {type(parsed).__name__}"
        raise ParseError(msg)

    out: list[T] = []
    dropped: list[str] = []
    for idx, entry in enumerate(parsed):
        if not isinstance(entry, dict):
            dropped.append(str(idx))
            continue
        entry_dict = {str(k): v for k, v in entry.items()}
        result = item(entry_dict)
        if result is None:
            dropped.append(str(idx))
            continue
        out.append(result)
    if dropped:
        emit_wobble(
            boundary=boundary,
            field=f"items[{','.join(dropped)}]",
            tolerance=WobbleTolerance.DEFAULT,
            model=model,
            raw_excerpt=raw,
            logger=logger,
        )
    return Wobbled(_Parsed(value=out, recovered_fields=tuple(dropped)))


__all__ = (
    "ParseError",
    "WobblePolicy",
    "WobbleSkip",
    "WobbleTolerance",
    "Wobbled",
    "emit_wobble",
    "parse_list_with_policy",
    "parse_with_policy",
    "recovered_fields",
    "strip_fenced_blocks",
    "unwrap",
)
