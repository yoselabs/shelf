"""Reflect an argparse parser into FastMCP tools and run calls through the caller's `run`.

argparse has no public way to enumerate a parser's actions or subcommands, so this module reads its private
names (`_actions`, `_SubParsersAction`, ...), the same ones verb-cli's testing helper reads.
"""

# ruff: noqa: SLF001

import argparse
import contextlib
import inspect
import io
from collections.abc import Callable
from typing import Annotated, Literal

from fastmcp.tools import FunctionTool, Tool
from pydantic import BaseModel, Field

Run = Callable[[list[str]], tuple[int, list[str]]]
_SKIP = (argparse._HelpAction, argparse._SubParsersAction)


class Result(BaseModel):
    """What a command printed, and how it ended (the caller's exit code; usage errors use `usage`)."""

    exit_code: int
    output: str


def _own(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [a for a in parser._actions if not isinstance(a, _SKIP)]


def _is_flag(action: argparse.Action) -> bool:
    return action.nargs == 0 and not isinstance(action, argparse._CountAction)


def _many(action: argparse.Action) -> bool:
    return isinstance(action, argparse._AppendAction) or action.nargs in ("*", "+") or (isinstance(action.nargs, int) and action.nargs > 1)


def _kind(action: argparse.Action) -> object:
    if _is_flag(action):
        return bool
    if isinstance(action, argparse._CountAction):
        return int
    if action.choices:
        return Literal[tuple(action.choices)]  # pyrefly: ignore[invalid-literal] — a runtime enum of the choices
    item = action.type if action.type in (int, float) else str
    return list[item] if _many(action) else item


def _required(action: argparse.Action) -> bool:
    if action.option_strings:
        return action.required
    return action.nargs not in ("?", "*")


def _parameter(action: argparse.Action) -> inspect.Parameter:
    required = _required(action)
    note = action.help or action.dest
    if action.default not in (None, argparse.SUPPRESS) and not required:
        note += f" (default {action.default})"
    kind = Annotated[_kind(action), Field(description=note)]  # pyrefly: ignore[invalid-annotation] — built at runtime
    return inspect.Parameter(
        action.dest,
        inspect.Parameter.KEYWORD_ONLY,
        annotation=kind if required else kind | None,
        default=inspect.Parameter.empty if required else None,
    )


def _argv(actions: list[argparse.Action], values: dict[str, object]) -> list[str]:
    argv: list[str] = []
    for action in actions:
        value = values.get(action.dest)
        if value is None or value is False:
            continue
        flag = action.option_strings[0] if action.option_strings else None
        if isinstance(value, list):
            repeat = isinstance(action, argparse._AppendAction)
            for index, item in enumerate(value):
                if flag and (repeat or index == 0):
                    argv.append(flag)
                argv.append(str(item))
        elif isinstance(action, argparse._CountAction):
            argv += [flag] * int(str(value)) if flag else []
        else:
            if flag:
                argv.append(flag)
            if not _is_flag(action):
                argv.append(str(value))
    return argv


def _run(run: Run, argv: list[str], usage: int) -> Result:
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            code, lines = run(argv)
    except SystemExit as stop:  # argparse rejected the input; it printed why to stderr
        code, lines = usage, [err.getvalue().strip() or f"usage error ({stop.code})"]
    return Result(exit_code=code, output="\n".join(lines))


def _callable(name: str, shared: list[argparse.Action], sub: argparse.ArgumentParser, run: Run, usage: int) -> Callable[..., Result]:
    own = _own(sub)
    taken = {a.dest for a in own}
    outer = [a for a in shared if a.dest not in taken]
    positional = [a for a in own if not a.option_strings]
    options = [a for a in own if a.option_strings]

    def call(**values: object) -> Result:
        # global options precede the command; positionals follow the command's own options, in order
        return _run(run, [*_argv(outer, values), name, *_argv(options, values), *_argv(positional, values)], usage)

    params = [_parameter(a) for a in [*positional, *options, *[a for a in outer if a.option_strings]]]
    call.__signature__ = inspect.Signature(params, return_annotation=Result)  # type: ignore[attr-defined]
    call.__annotations__ = {p.name: p.annotation for p in params} | {"return": Result}
    return call


def _description(sub: argparse.ArgumentParser) -> str:
    return sub.description or " ".join(sub.format_usage().split())


def tools_from_parser(parser: argparse.ArgumentParser, run: Run, *, usage: int = 2) -> list[Tool]:
    """One tool per subcommand of `parser`; its own options are folded into every tool."""
    shared = _own(parser)
    tools: list[Tool] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                fn = _callable(name, shared, sub, run, usage)
                tools.append(FunctionTool.from_function(fn, name=name, description=_description(sub)))
    return tools
