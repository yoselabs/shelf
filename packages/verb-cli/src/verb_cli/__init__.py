"""A function signature becomes CLI flags, and parsed flags become its keyword arguments.

- :func:`flags_of` reads one :class:`FlagSpec` per parameter: ``Annotated[..., Field(alias=)]``
  names the flag, ``Field(description=)`` is the help (else a type label such as ``text``), ``T | None`` is ``T``, and a type
  outside the scalars (``str``, ``int``, ``float``, ``bool``, ``Path``) is one JSON flag.
- :func:`to_argparse` adds the flags to a parser; ``bool`` is a paired ``--flag/--no-flag``.
  ``Annotated[T, POSITIONAL]`` is a positional argument (``*args`` too, as ``nargs="*"``);
  ``choice_flags_of(fn)`` is ``flags_of`` that maps a ``Literal`` or ``Enum`` to argparse choices.
- :class:`VerbCli` turns ``{name: fn}`` into one parser with a subparser per verb, folds a shared
  parameter class (``--repo``, ``--kb``) into every verb, and parses argv into an :class:`Invocation`.
- :func:`kwargs_of` turns the parsed namespace into keyword arguments, decoding JSON flags
  and validating a model; invalid JSON raises :class:`FlagJsonError`.

Metadata is duck-typed (``alias``, ``description``, ``model_validate``), so pydantic is
what the caller annotates with, not what this module imports.
"""

from __future__ import annotations

import argparse
import enum
import inspect
import json
import types
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class _Positional:
    """Marker: ``Annotated[str, POSITIONAL]`` makes the parameter a positional argument, not a flag."""

    def __repr__(self) -> str:
        return "POSITIONAL"


POSITIONAL = _Positional()

_SCALAR_TYPES = (str, int, float, bool, Path)
_CONVERTED = (int, float, Path)
_LABELS: tuple[tuple[type | tuple[type, ...], str], ...] = (
    (bool, "true or false"),
    (Path, "path"),
    (int, "integer"),
    (float, "number"),
    (str, "text"),
    ((list, tuple, set, frozenset), "JSON array"),
    (dict, "JSON object"),
)


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
    base: Any  # Any: a verb's parameters and defaults are of any type
    needs_json: bool
    required: bool
    default: Any  # Any: a verb's parameters and defaults are of any type
    help: str | None
    positional: bool = False
    variadic: bool = False
    choices: tuple[Any, ...] | None = None  # Any: a verb's parameters and defaults are of any type
    enum: Any = None  # Any: a verb's parameters and defaults are of any type


def _strip_optional(ann: Any) -> Any:
    """``T | None`` / ``Optional[T]`` → ``T``; other annotations pass through unchanged."""
    if isinstance(ann, types.UnionType) or typing.get_origin(ann) is typing.Union:
        non_none = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return ann


def _type_label(base: Any) -> str:
    """The help of a parameter with no description: what kind of value the flag takes."""
    origin = typing.get_origin(base) or base
    if not isinstance(origin, type):
        return "JSON value"
    for kind, label in _LABELS:  # bool before int: bool is an int
        if issubclass(origin, kind):
            return label
    return "JSON object" if hasattr(origin, "model_validate") else "JSON value"


def _choices_of(base: Any) -> tuple[tuple[Any, ...] | None, Any]:
    """The closed set of values of a ``Literal`` or an ``Enum`` (by value), else ``(None, None)``."""
    if typing.get_origin(base) is typing.Literal:
        values = typing.get_args(base)
        return (values, None) if values and len({type(v) for v in values}) == 1 else (None, None)
    if isinstance(base, type) and issubclass(base, enum.Enum):
        values = tuple(m.value for m in base)
        return (values, base) if values and len({type(v) for v in values}) == 1 else (None, None)
    return None, None


def _analyze(pname: str, ann: Any) -> tuple[str, Any, bool, str | None, bool]:
    """One parameter → ``(flag, base type, needs JSON, help, positional)``."""
    alias: str | None = None
    help_text: str | None = None
    positional = False
    if hasattr(ann, "__metadata__"):  # Annotated[base, FieldInfo, ...]
        for meta in ann.__metadata__:
            alias = alias or getattr(meta, "alias", None)
            help_text = help_text or getattr(meta, "description", None)
            positional = positional or meta is POSITIONAL
        ann = ann.__origin__
    base = _strip_optional(ann)
    help_text = help_text or _type_label(base)
    flag = f"--{(alias or pname).replace('_', '-')}"
    is_scalar = isinstance(base, type) and issubclass(base, _SCALAR_TYPES)
    return flag, base, not is_scalar, help_text, positional


def _no_choices(_base: Any) -> tuple[tuple[Any, ...] | None, Any]:
    return None, None


def flags_of(fn: Callable[..., Any]) -> list[FlagSpec]:  # Any: a verb's parameters and defaults are of any type
    """One :class:`FlagSpec` per parameter of ``fn``, in signature order.

    String annotations (``from __future__ import annotations``) are resolved with their
    ``Annotated`` metadata. ``self`` and ``**kwargs`` are skipped, and so is ``*args`` unless it is
    marked :data:`POSITIONAL`. A class works as well as a function (its ``__init__`` signature).
    A ``Literal`` or an ``Enum`` is one JSON flag; :func:`choice_flags_of` makes it argparse choices.
    """
    return _flags(fn, _no_choices)


def choice_flags_of(fn: Callable[..., Any]) -> list[FlagSpec]:  # Any: a verb's parameters and defaults are of any type
    """:func:`flags_of` that turns a ``Literal`` or an ``Enum`` of one value type into argparse choices instead of a JSON flag."""
    return _flags(fn, _choices_of)


def _flags(fn: Callable[..., Any], choices_of: Callable[[Any], tuple[tuple[Any, ...] | None, Any]]) -> list[FlagSpec]:
    hints = typing.get_type_hints(fn, include_extras=True)
    specs: list[FlagSpec] = []
    for pname, param in inspect.signature(fn).parameters.items():
        if pname == "self" or param.kind is param.VAR_KEYWORD:
            continue
        flag, base, needs_json, help_text, positional = _analyze(pname, hints.get(pname, str))
        variadic = param.kind is param.VAR_POSITIONAL
        if variadic and not positional:
            continue
        values, enum_type = choices_of(base)
        if values is not None:
            needs_json = False
        if positional and base is bool:
            message = f"{pname}: a bool is a flag, not a positional argument"
            raise VerbCliError(message)
        required = param.default is inspect.Parameter.empty and not variadic
        specs.append(
            FlagSpec(
                dest=pname,
                flag=flag,
                base=base,
                needs_json=needs_json,
                required=required,
                default=None if required or variadic else param.default,
                help=help_text,
                positional=positional,
                variadic=variadic,
                choices=values,
                enum=enum_type,
            )
        )
    return specs


def _converter(spec: FlagSpec) -> Any:
    if spec.choices is not None:
        return type(spec.choices[0]) if type(spec.choices[0]) in _CONVERTED else str
    return spec.base if spec.base in _CONVERTED else str


def _add_positional(parser: argparse.ArgumentParser, spec: FlagSpec) -> None:
    kwargs: dict[str, Any] = {"metavar": spec.flag.lstrip("-"), "help": spec.help}
    if spec.needs_json:
        kwargs["default"] = None
    else:
        kwargs["type"] = _converter(spec)
        kwargs["choices"] = spec.choices
    if spec.variadic:
        kwargs["nargs"] = "*"
    elif not spec.required:
        kwargs["nargs"] = "?"
        kwargs.setdefault("default", spec.default)
    parser.add_argument(spec.dest, **kwargs)


def to_argparse(parser: argparse.ArgumentParser, specs: list[FlagSpec]) -> None:
    """Add one argument per spec to ``parser``."""
    for spec in specs:
        if spec.positional:
            _add_positional(parser, spec)
        elif spec.base is bool and not spec.needs_json:
            action = argparse.BooleanOptionalAction
            parser.add_argument(spec.flag, dest=spec.dest, action=action, default=spec.default, required=spec.required, help=spec.help)
        elif spec.needs_json:
            # No default here: a flag left out is left out of the call, so the function's
            # own default applies, and a default is never decoded as JSON.
            parser.add_argument(spec.flag, dest=spec.dest, default=None, required=spec.required, help=spec.help)
        else:
            parser.add_argument(
                spec.flag,
                dest=spec.dest,
                type=_converter(spec),
                choices=spec.choices,
                default=spec.default,
                required=spec.required,
                help=spec.help,
            )


def kwargs_of(ns: argparse.Namespace, specs: list[FlagSpec]) -> dict[str, Any]:  # Any: a verb's parameters and defaults are of any type
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
        if spec.enum is not None and value is not None:
            value = spec.enum(value)
        kwargs[spec.dest] = value
    return kwargs


from verb_cli.verbs import Invocation, VerbCli  # noqa: E402  (verbs builds on the names above)

__all__ = [
    "POSITIONAL",
    "FlagJsonError",
    "FlagSpec",
    "Invocation",
    "VerbCli",
    "VerbCliError",
    "choice_flags_of",
    "flags_of",
    "kwargs_of",
    "to_argparse",
]
