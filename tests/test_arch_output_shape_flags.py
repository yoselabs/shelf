"""Article IX check: no public function takes a flag that selects its RETURN SHAPE.

A parameter named like mode/format/compact/raw/verbose/full/pretty/as_* (any annotation) is a hit when it
changes what the function returns: the function is `@overload`ed on it, its return annotation is a union
of shapes and the parameter is tested, or two returns guarded by that parameter build visibly different
values. The cure is one lossless value plus separate pure view functions. Known hits are listed in
`_KNOWN` with the reason each stands; a new hit fails the gate, a vanished one must leave the list.
"""

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_FLAG = re.compile(r"^(mode|fmt|format|output_format|compact|raw|verbose|full|pretty|style|view|shape|detail|brief|plain|as_\w+)$")


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _shape(expr: ast.expr | None) -> str | None:  # noqa: PLR0911 -- one return per recognised syntax kind
    """A coarse, certain kind of the built value, or None when it cannot be told from the syntax."""
    match expr:
        case ast.Constant(value=None):
            return None
        case ast.Constant(value=value):
            return type(value).__name__
        case ast.JoinedStr():
            return "str"
        case ast.Dict() | ast.DictComp():
            return "dict"
        case ast.List() | ast.ListComp():
            return "list"
        case ast.Tuple():
            return "tuple"
        case ast.Call(func=ast.Name(id=name)) if name in {"str", "dict", "list", "tuple", "int", "bytes"}:
            return name
        case ast.Call(func=ast.Attribute(attr="join")):
            return "str"
        case _:
            return None


def _guarded_returns(body: list[ast.stmt], flag: str, *, guarded: bool = False) -> list[tuple[bool, str | None]]:
    """(guarded by the flag, shape) for every returned value in `body`, nested defs excluded."""
    found: list[tuple[bool, str | None]] = []
    for stmt in body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if isinstance(stmt, ast.Return):
            value = stmt.value
            if isinstance(value, ast.IfExp) and flag in _names(value.test):
                found += [(True, _shape(value.body)), (True, _shape(value.orelse))]
            else:
                found.append((guarded, _shape(value)))
        elif isinstance(stmt, ast.If):
            inner = guarded or flag in _names(stmt.test)
            found += _guarded_returns(stmt.body, flag, guarded=inner) + _guarded_returns(stmt.orelse, flag, guarded=inner)
        else:
            for field in ("body", "orelse", "finalbody"):
                found += _guarded_returns(getattr(stmt, field, []) or [], flag, guarded=guarded)
            for handler in getattr(stmt, "handlers", []):
                found += _guarded_returns(handler.body, flag, guarded=guarded)
            for case in getattr(stmt, "cases", []):
                found += _guarded_returns(case.body, flag, guarded=guarded or flag in _names(stmt))
    return found


def _union_members(annotation: ast.expr | None) -> int:
    if annotation is None:
        return 0
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _union_members(annotation.left) + _union_members(annotation.right)
    return 0 if isinstance(annotation, ast.Constant) and annotation.value is None else 1


def _is_overload(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(ast.unparse(d).split(".")[-1] == "overload" for d in func.decorator_list)


def _why(func: ast.FunctionDef | ast.AsyncFunctionDef, arg: ast.arg, overloaded: set[str]) -> str | None:
    flag = arg.arg
    if func.name == "__init__":
        return "constructor bool stored as an output switch" if arg.annotation and ast.unparse(arg.annotation) == "bool" else None
    if func.name in overloaded:
        return "overloaded on it"
    tested = any(flag in _names(n.test) for n in ast.walk(func) if isinstance(n, ast.If | ast.IfExp))
    if tested and _union_members(func.returns) >= 2:
        return "union return annotation, flag tested"
    returns = _guarded_returns(func.body, flag)
    shapes = {s for _, s in returns if s} if any(guarded for guarded, _ in returns) else set()
    return "guarded returns build different values" if len(shapes) >= 2 else None


def shape_flags(root: Path) -> dict[str, str]:
    """`package:function:flag` -> why, for every public function in `root/packages/*/src` with a hit."""
    hits: dict[str, str] = {}
    for path in sorted((root / "packages").glob("*/src/**/*.py")):
        package = path.relative_to(root / "packages").parts[0]
        funcs = [n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
        overloaded = {f.name for f in funcs if _is_overload(f)}
        for func in funcs:
            if func.name.startswith("_") and func.name != "__init__":
                continue
            args = func.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                if _FLAG.match(arg.arg) and (why := _why(func, arg, overloaded)):
                    hits[f"{package}:{func.name}:{arg.arg}"] = why
    return hits


_KNOWN: dict[str, str] = {}


def _plant(tmp_path: Path, source: str) -> dict[str, str]:
    module = tmp_path / "packages" / "pkg" / "src" / "pkg" / "mod.py"
    module.parent.mkdir(parents=True)
    module.write_text(source)
    return shape_flags(tmp_path)


def test_repo_has_no_unlisted_output_shape_flag() -> None:
    new = sorted(set(shape_flags(_ROOT)) - set(_KNOWN))
    assert not new, f"a parameter selects the return shape (Article IX: one lossless value, views as pure functions): {new}"


def test_known_hits_are_still_hits_and_carry_a_reason() -> None:
    assert not sorted(set(_KNOWN) - set(shape_flags(_ROOT))), "a listed hit no longer exists: delete its row"
    assert all(reason.strip() for reason in _KNOWN.values())


def test_planted_overload_on_a_flag_fails(tmp_path: Path) -> None:
    source = (
        "from typing import Literal, overload\n"
        "@overload\ndef load(p: str, *, fmt: Literal['text']) -> str: ...\n"
        "@overload\ndef load(p: str, *, fmt: Literal['bytes']) -> bytes: ...\n"
        "def load(p, *, fmt): return p\n"
    )
    assert _plant(tmp_path, source) == {"pkg:load:fmt": "overloaded on it"}


def test_planted_union_return_selected_by_a_flag_fails(tmp_path: Path) -> None:
    source = "def show(x: int, compact: bool = False) -> str | dict[str, int]:\n    return str(x) if compact else {'x': x}\n"
    assert set(_plant(tmp_path, source)) == {"pkg:show:compact"}


def test_planted_branches_building_different_values_fail(tmp_path: Path) -> None:
    source = "def show(x, verbose=False):\n    if verbose:\n        return {'x': x}\n    return f'{x}'\n"
    assert set(_plant(tmp_path, source)) == {"pkg:show:verbose"}


def test_planted_constructor_bool_switch_fails(tmp_path: Path) -> None:
    source = "class Wire:\n    def __init__(self, *, pretty: bool = False) -> None:\n        self.pretty = pretty\n"
    assert set(_plant(tmp_path, source)) == {"pkg:__init__:pretty"}


def test_same_return_type_and_raw_input_params_pass(tmp_path: Path) -> None:
    source = (
        "from typing import Literal\n"
        "def reset(mode: Literal['soft', 'hard']) -> None:\n    if mode == 'soft':\n        return None\n"
        "def parse(raw: bytes) -> list[int]:\n    return list(raw)\n"
        "def _private(compact: bool) -> str | int:\n    return 1 if compact else 'a'\n"
    )
    assert _plant(tmp_path, source) == {}
