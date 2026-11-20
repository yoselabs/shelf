"""A set of verbs (``{name: function}``) becomes one parser with a subparser per verb.

:class:`VerbCli` is built once from the verbs and an optional ``shared`` class (a dataclass or
any class whose ``__init__`` signature names the parameters). The shared parameters become flags on
every verb; a verb that declares a parameter annotated with that class receives the built instance.
``VerbCli.specs(name)`` is the verb's own flags (shared ones excluded), for a surface other than argv.
"""

from __future__ import annotations

import argparse
import inspect
import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import verb_cli as vc

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Invocation:
    """A parsed command line: which verb, and the exact arguments to call it with."""

    name: str
    fn: Callable[..., Any]  # Any: a verb's parameters and defaults are of any type
    args: tuple[Any, ...]  # Any: a verb's parameters and defaults are of any type
    kwargs: dict[str, Any]  # Any: a verb's parameters and defaults are of any type
    shared: Any = None  # Any: a verb's parameters and defaults are of any type

    def call(self) -> Any:  # Any: a verb's parameters and defaults are of any type
        """Call the verb. A coroutine function returns its coroutine, for the caller to await."""
        return self.fn(*self.args, **self.kwargs)


def _first_line(text: str | None) -> str | None:
    lines = inspect.cleandoc(text or "").splitlines()
    return lines[0] if lines else None


class VerbCli:
    """One parser from ``{name: fn}``; ``shared`` is folded into every verb."""

    def __init__(
        self, verbs: Mapping[str, Callable[..., Any]], *, shared: type | None = None
    ) -> None:  # Any: a verb's parameters and defaults are of any type
        self.verbs = dict(verbs)
        self.shared = shared
        self._shared_specs = vc.flags_of(shared, choices=True) if shared is not None else []
        self._specs: dict[str, list[vc.FlagSpec]] = {}
        for name, fn in self.verbs.items():
            specs = [s for s in vc.flags_of(fn, choices=True) if shared is None or s.base is not shared]
            clash = {s.dest for s in specs} & {s.dest for s in self._shared_specs}
            if clash:
                message = f"{name}: parameter {sorted(clash)} is also a shared parameter"
                raise vc.VerbCliError(message)
            self._specs[name] = specs

    def specs(self, name: str) -> list[vc.FlagSpec]:
        """The verb's own flags and positionals, shared parameters excluded."""
        return list(self._specs[name])

    def parser(self, *, prog: str | None = None, description: str | None = None) -> argparse.ArgumentParser:
        """The parser: one subparser per verb, its help the first line of the docstring."""
        parser = argparse.ArgumentParser(prog=prog, description=description or "Commands.")
        sub = parser.add_subparsers(dest="_verb", metavar="command", required=True)
        for name, fn in self.verbs.items():
            doc = inspect.getdoc(fn)
            child = sub.add_parser(
                name, help=_first_line(doc) or name, description=doc or name, formatter_class=argparse.RawDescriptionHelpFormatter
            )
            vc.to_argparse(child, [*self._specs[name], *self._shared_specs])
        return parser

    def invocation(self, ns: argparse.Namespace) -> Invocation:
        """The call a parsed namespace asks for."""
        name: str = ns._verb  # noqa: SLF001
        fn = self.verbs[name]
        kwargs = vc.kwargs_of(ns, self._specs[name])
        shared = self.shared(**vc.kwargs_of(ns, self._shared_specs)) if self.shared is not None else None
        if shared is not None:
            hints = typing.get_type_hints(fn)
            kwargs.update({pname: shared for pname, hint in hints.items() if hint is self.shared})
        args = _positional_args(fn, kwargs)
        return Invocation(name, fn, args, kwargs, shared)

    def parse(self, argv: Sequence[str] | None = None, *, prog: str | None = None) -> Invocation:
        """Parse ``argv`` (argparse exits with 2 on a refusal, as usual)."""
        return self.invocation(self.parser(prog=prog).parse_args(argv))


def _positional_args(fn: Callable[..., Any], kwargs: dict[str, Any]) -> tuple[Any, ...]:
    """Move arguments into positions when the verb takes ``*args`` or positional-only ones; else all stay keywords."""
    params = inspect.signature(fn).parameters
    var = next((n for n, p in params.items() if p.kind is p.VAR_POSITIONAL), None)
    if var is None and not any(p.kind is p.POSITIONAL_ONLY for p in params.values()):
        return ()
    args: list[Any] = []
    for pname, param in params.items():
        if var is not None and pname == var:
            args.extend(kwargs.pop(pname, None) or [])
            break
        if param.kind is param.POSITIONAL_ONLY or (var is not None and param.kind is param.POSITIONAL_OR_KEYWORD):
            args.append(kwargs.pop(pname, param.default))
    return tuple(args)
