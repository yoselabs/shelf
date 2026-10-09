"""A function signature becomes CLI flags, and parsed flags become its keyword arguments.

- :func:`flags_of` reads one :class:`FlagSpec` per parameter: ``Annotated[..., Field(alias=)]``
  names the flag, ``Field(description=)`` is the help, ``T | None`` is ``T``, and a type
  outside the scalars (``str``, ``int``, ``float``, ``bool``, ``Path``) is one JSON flag.
- :func:`to_argparse` adds the flags to a parser; ``bool`` is a paired ``--flag/--no-flag``.
- :func:`kwargs_of` turns the parsed namespace into keyword arguments, decoding JSON flags
  and validating a model; invalid JSON raises :class:`FlagJsonError`.

Metadata is duck-typed (``alias``, ``description``, ``model_validate``), so pydantic is
what the caller annotates with, not what this module imports.
"""

from __future__ import annotations

import argparse
import inspect
import json
import types
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

_SCALAR_TYPES = (str, int, float, bool, Path)
_CONVERTED = (int, float, Path)


class VerbCliError(Exception):
    """A refusal of a command line."""


class FlagJsonError(VerbCliError):
    """A JSON flag whose value does not parse; :attr:`flag` names it."""

    def __init__(self, flag: str, value: str, cause: json.JSONDecodeError) -> None:
        self.flag = flag
        self.value = value
        super().__init__(f"{flag}: invalid JSON ({cause})")


@dataclass(frozen=True, slots=True)
class FlagSpec:
    """One parameter as a flag. ``dest`` is the parameter name; ``flag`` is what a user types."""

    dest: str
    flag: str
    base: Any
    needs_json: bool
    required: bool
    default: Any
    help: str | None


def _strip_optional(ann: Any) -> Any:
    """``T | None`` / ``Optional[T]`` → ``T``; other annotations pass through unchanged."""
    if isinstance(ann, types.UnionType) or typing.get_origin(ann) is typing.Union:
        non_none = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return ann


def _analyze(pname: str, ann: Any) -> tuple[str, Any, bool, str | None]:
    """One parameter → ``(flag, base type, needs JSON, help)``."""
    alias: str | None = None
    help_text: str | None = None
    if hasattr(ann, "__metadata__"):  # Annotated[base, FieldInfo, ...]
        for meta in ann.__metadata__:
            alias = alias or getattr(meta, "alias", None)
            help_text = help_text or getattr(meta, "description", None)
        ann = ann.__origin__
    base = _strip_optional(ann)
    flag = f"--{(alias or pname).replace('_', '-')}"
    is_scalar = isinstance(base, type) and issubclass(base, _SCALAR_TYPES)
    return flag, base, not is_scalar, help_text


def flags_of(fn: Callable[..., Any]) -> list[FlagSpec]:
    """One :class:`FlagSpec` per parameter of ``fn``, in signature order.

    String annotations (``from __future__ import annotations``) are resolved with their
    ``Annotated`` metadata. ``self``, ``*args`` and ``**kwargs`` are skipped.
    """
    hints = typing.get_type_hints(fn, include_extras=True)
    specs: list[FlagSpec] = []
    for pname, param in inspect.signature(fn).parameters.items():
        if pname == "self" or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        flag, base, needs_json, help_text = _analyze(pname, hints.get(pname, str))
        required = param.default is inspect.Parameter.empty
        specs.append(
            FlagSpec(
                dest=pname,
                flag=flag,
                base=base,
                needs_json=needs_json,
                required=required,
                default=None if required else param.default,
                help=help_text,
            )
        )
    return specs


def to_argparse(parser: argparse.ArgumentParser, specs: list[FlagSpec]) -> None:
    """Add one argument per spec to ``parser``."""
    for spec in specs:
        if spec.base is bool and not spec.needs_json:
            action = argparse.BooleanOptionalAction
            parser.add_argument(spec.flag, dest=spec.dest, action=action, default=spec.default, required=spec.required, help=spec.help)
        elif spec.needs_json:
            # No default here: a flag left out is left out of the call, so the function's
            # own default applies, and a default is never decoded as JSON.
            parser.add_argument(spec.flag, dest=spec.dest, default=None, required=spec.required, help=spec.help or "a JSON value")
        else:
            convert = spec.base if spec.base in _CONVERTED else str
            parser.add_argument(spec.flag, dest=spec.dest, type=convert, default=spec.default, required=spec.required, help=spec.help)


def kwargs_of(ns: argparse.Namespace, specs: list[FlagSpec]) -> dict[str, Any]:
    """The keyword arguments ``ns`` holds: JSON flags decoded, a model validated, a JSON flag left out omitted."""
    kwargs: dict[str, Any] = {}
    for spec in specs:
        value = getattr(ns, spec.dest)
        if spec.needs_json and value is None:
            continue
        if spec.needs_json and isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise FlagJsonError(spec.flag, value, exc) from exc
            validate = getattr(spec.base, "model_validate", None) if isinstance(spec.base, type) else None
            if validate is not None:
                value = validate(value)
        kwargs[spec.dest] = value
    return kwargs


__all__ = ["FlagJsonError", "FlagSpec", "VerbCliError", "flags_of", "kwargs_of", "to_argparse"]
