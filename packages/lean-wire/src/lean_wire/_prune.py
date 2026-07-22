"""``PruneEmpty`` base class — opt-in empty-field pruning on the wire.

pydantic serializes with ``model_dump(mode="json")`` by default, which emits
every optional field even when empty (``byline: null``, ``next_links: []``). On
token-sensitive tools (agent-facing endpoints generally) that is pure noise in
the calling agent's context.

The opt-in is a **pydantic base class** that installs a
``@model_serializer(mode="wrap")`` dropping keys whose value is ``None``, ``""``,
``[]``, or ``{}``. Other zero-valued types (``0``, ``False``, ``Decimal(0)``,
empty ``frozenset``) are KEPT — they carry information.

Cascades through nested models naturally: pydantic uses each model's own
serializer when serializing a parent model's nested field. So a ``PruneEmpty``
subclass nested inside a non-pruning parent still gets pruned.

The pruning leaves the JSON schema unchanged: ``outputSchema`` advertises the
fields as optional regardless. The wire payload is the only thing affected.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, SerializerFunctionWrapHandler, model_serializer


def _is_empty(value: Any) -> bool:
    """Empty per the marker spec: ``None`` / ``""`` / ``[]`` / ``{}``.

    Non-empty: ``0``, ``False``, ``Decimal(0)``, empty ``frozenset``, etc. Only
    the four literal empty containers + ``None`` qualify.
    """
    if value is None:
        return True
    return isinstance(value, (str, list, dict)) and len(value) == 0


def prune_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop empty values from the top level of ``payload``. Non-recursive by design."""
    return {k: v for k, v in payload.items() if not _is_empty(v)}


class PruneEmpty(BaseModel):
    """Base for wire-facing pydantic models that should drop empty fields.

    Inherit instead of ``BaseModel``::

        from lean_wire import PruneEmpty

        class AskExtraction(PruneEmpty):
            truncated: bool
            model: str | None = None
            cost_usd: float | None = None

    When dumped (directly or nested under a non-pruning parent), the empty fields
    (``None`` / ``""`` / ``[]`` / ``{}``) are omitted. Required-but-falsy fields
    (``truncated: False``, ``count: 0``) are KEPT — empty-container semantics only.

    Subclasses that define their own ``@model_serializer`` override this one
    (pydantic supports only one model_serializer per class). In that case the
    subclass is responsible for any pruning it wants.
    """

    @model_serializer(mode="wrap")
    def _prune(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return prune_dict(handler(self))


def dump_model_for_wire(model: BaseModel) -> dict[str, Any]:
    """``model.model_dump(mode="json")`` — the single substrate helper for wire dumps.

    With ``PruneEmpty`` doing the work via pydantic's native serializer cascade,
    this is a thin wrapper. Kept as the substrate seam so consumers have one
    obvious entry point and future wire-shaping can be added in one place.
    """
    return model.model_dump(mode="json")


__all__ = ["PruneEmpty", "dump_model_for_wire", "prune_dict"]
