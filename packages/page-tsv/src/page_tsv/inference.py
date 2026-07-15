"""Type-driven format-hint inference.

Given a tool's resolved return-type annotation, ``infer_format_hint`` returns
``"tsv" | "json" | "page-tsv"`` deterministically. JSON is the safe default for
any input the inference can't positively prove tabular — missing annotations,
``Any``, ``Union`` shapes, unresolved forward refs, etc.

Leaf module: imports only stdlib + pydantic + ``response`` (for ``Page``).
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel

from page_tsv.response import Page

FormatHintInferred = Literal["tsv", "json", "page-tsv"]

_DUMP_SCALAR_TYPES: tuple[type, ...] = (
    str,
    int,
    float,
    bool,
    bytes,
    datetime,
    date,
    time,
    Decimal,
    UUID,
)


def is_basemodel(ann: Any) -> type[BaseModel] | None:
    """Return the BaseModel subclass if ``ann`` (or its inner Annotated/Optional/Union) is one.

    Truthy-friendly: callers that only want a bool can use ``if is_basemodel(x):``.
    Callers that want the class itself (e.g. to call ``model_validate`` on it) can
    use the returned type.

    Unwraps ``Annotated[T, ...]``, ``Optional[T]``, and ``Union[T1, T2, ...]``
    recursively. Returns ``None`` for plain ``dict``, scalars, or types that
    aren't BaseModel after unwrapping.
    """
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return ann
    if hasattr(ann, "__metadata__"):
        inner = get_args(ann)[0]
        return is_basemodel(inner)
    origin = get_origin(ann)
    if origin is Union or origin is types.UnionType:
        for a in get_args(ann):
            if a is type(None):
                continue
            found = is_basemodel(a)
            if found is not None:
                return found
    return None


def _is_pep604_union(annotation: Any) -> bool:
    # ``str | None`` produces ``types.UnionType``, distinct from typing.Union.
    return isinstance(annotation, types.UnionType)


def _is_dump_scalar(annotation: Any) -> bool:  # noqa: PLR0911
    """Return True iff ``annotation`` dumps to a primitive scalar.

    Unwraps ``Optional`` / ``Annotated`` / ``Literal`` first; a scalar is a type
    that ``BaseModel.model_dump(mode="json")`` produces as a primitive.
    """
    if annotation is None or annotation is type(None):
        return True

    origin = get_origin(annotation)

    # Annotated[T, ...] — unwrap to T
    if origin is not None and getattr(annotation, "__metadata__", None) is not None:
        return _is_dump_scalar(get_args(annotation)[0])

    # Literal[...] — every literal value is a scalar by construction
    if origin is Literal:
        return True

    # Union[...] / Optional[...] — every branch must be scalar
    if origin is Union or _is_pep604_union(annotation):
        return all(_is_dump_scalar(a) for a in get_args(annotation))

    # Bare type — direct membership or Enum subclass
    if isinstance(annotation, type):
        if annotation in _DUMP_SCALAR_TYPES:
            return True
        return issubclass(annotation, Enum)

    # Parameterized generics (list[str], dict[...], tuple[...]) → not scalar
    return False


def _model_is_scalar_only(cls: type[BaseModel]) -> bool:
    return all(_is_dump_scalar(model_field.annotation) for model_field in cls.model_fields.values())


def infer_format_hint(return_type: Any) -> FormatHintInferred:  # noqa: PLR0911
    """Map a resolved return-type annotation to a wire-format hint.

    Defaults to ``"json"`` whenever the type is missing, ambiguous, or not
    positively provable as tabular.
    """
    if return_type is None or return_type is Any:
        return "json"

    origin = get_origin(return_type)

    # Page[T] (or subclass) — hybrid envelope
    if origin is None and isinstance(return_type, type) and issubclass(return_type, Page):
        item_type = _page_item_type(return_type)
        if item_type is not None and is_basemodel(item_type) and _model_is_scalar_only(item_type):
            return "page-tsv"
        return "json"

    if origin is not None and isinstance(origin, type) and issubclass(origin, Page):
        args = get_args(return_type)
        if len(args) == 1 and is_basemodel(args[0]) and _model_is_scalar_only(args[0]):
            return "page-tsv"
        return "json"

    # list[T] / tuple[T] — TSV when T is scalar-only BaseModel
    if origin in (list, tuple):
        args = get_args(return_type)
        # a variable-length homogeneous tuple (one arg then Ellipsis) is TSV-able on
        # its element type; a fixed-length heterogeneous tuple is not.
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                args = (args[0],)
            else:
                return "json"
        if len(args) == 1 and is_basemodel(args[0]) and _model_is_scalar_only(args[0]):
            return "tsv"
        return "json"

    # Everything else (single BaseModel, dict, scalars, Union, Optional) → JSON
    return "json"


@dataclass(frozen=True)
class EncodingPlan:
    """Static plan for encoding a tool's return type for the ``llm`` consumer.

    ``kind`` is ``tsv`` (flat list), ``page-tsv`` (``Page[scalar-row]``),
    ``envelope`` (a ``BaseModel`` with flat-array fields named by ``tsv_fields``),
    or ``json``. A pure function of the annotation — it never inspects a runtime
    value.
    """

    kind: Literal["tsv", "page-tsv", "json", "envelope"]
    tsv_fields: tuple[str, ...] = field(default=())


def build_encoding_plan(return_type: Any) -> EncodingPlan:
    """Walk ``return_type`` and produce a static :class:`EncodingPlan`.

    Composes :func:`infer_format_hint` over the type and (one level down) its
    ``BaseModel`` fields.
    """
    hint = infer_format_hint(return_type)
    if hint == "tsv":
        return EncodingPlan("tsv")
    if hint == "page-tsv":
        return EncodingPlan("page-tsv")
    # hint == "json": dig one level for flat-array fields on a BaseModel.
    if is_basemodel(return_type):
        tsv_fields = tuple(
            name for name, model_field in return_type.model_fields.items() if infer_format_hint(model_field.annotation) == "tsv"
        )
        if tsv_fields:
            return EncodingPlan("envelope", tsv_fields=tsv_fields)
    return EncodingPlan("json")


def _page_item_type(cls: type[Page]) -> Any | None:
    """Extract the bound item type from a ``Page`` subclass, or None if bare.

    For ``class SearchPage(Page[Task])`` this returns ``Task``.
    Pydantic resolves the type variable into ``model_fields["items"].annotation``
    as ``list[Task]`` even when ``__pydantic_generic_metadata__`` is empty for a
    concrete subclass, so we read it off the field.
    """
    items_field = cls.model_fields.get("items")
    if items_field is None:
        return None
    items_ann = items_field.annotation
    if get_origin(items_ann) is list:
        args = get_args(items_ann)
        # Reject the bare TypeVar case (still T, not bound) — a typing.TypeVar has
        # no `mro`, so isinstance(args[0], type) is False.
        if len(args) == 1 and isinstance(args[0], type):
            return args[0]
    return None


__all__ = [
    "EncodingPlan",
    "FormatHintInferred",
    "build_encoding_plan",
    "infer_format_hint",
    "is_basemodel",
]
