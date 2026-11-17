"""Name Python code by symbol: spans, enclosing functions and source hashes, from the stdlib `ast`."""

import ast
import hashlib
import re
import textwrap
from dataclasses import dataclass

_Def = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
_LINES = re.compile(r"\r\n|\r|\n")

__all__ = ["Span", "find", "functions", "innermost", "symbol_hash"]


@dataclass(frozen=True)
class Span:
    """One symbol's place in a source: 1-based inclusive `start`..`end` lines (decorators included), its `text`
    (dedented when decorated or nested), and `body`, the first line of its body (equal to `start` for an assignment)."""

    name: str
    start: int
    end: int
    text: str
    body: int


def _span(source: str, name: str, node: ast.stmt) -> Span:
    decorators: list[ast.expr] = node.decorator_list if isinstance(node, _Def) else []
    start = min([node.lineno, *(item.lineno for item in decorators)])
    end = node.end_lineno or node.lineno
    lines = "\n".join(_LINES.split(source)[start - 1 : end])
    text = textwrap.dedent(lines) if decorators else ast.get_source_segment(source, node) or ""
    body = node.body[0].lineno if isinstance(node, _Def) else start
    return Span(name, start, end, text, body)


def _names(node: ast.stmt) -> list[str]:
    if isinstance(node, _Def):
        return [node.name]
    if isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
        return [node.name.id]
    if isinstance(node, ast.AnnAssign):
        targets: list[ast.expr] = [node.target]
    elif isinstance(node, ast.Assign):
        targets = list(node.targets)
    else:
        return []
    return [n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name)]


def _parse(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def find(source: str, symbol: str) -> Span | None:
    """The module-level def, class, assignment or type alias `symbol`; `Class.member` (any depth through classes)
    finds a member. None when absent or the source does not parse."""
    tree = _parse(source)
    if tree is None:
        return None
    body: list[ast.stmt] = tree.body
    node: ast.stmt | None = None
    *owners, last = symbol.split(".")
    for part in (*owners, last):
        if node is not None:
            if not isinstance(node, ast.ClassDef):
                return None
            body = node.body
        node = next((item for item in body if part in _names(item)), None)
        if node is None:
            return None
    return None if node is None else _span(source, symbol, node)


def functions(source: str) -> list[Span]:
    """Every function and method, qualified (`Class.method`, `outer.inner`), outer before inner; [] if unparsable."""
    tree = _parse(source)
    found: list[Span] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _Def):
                name = f"{prefix}{child.name}"
                if not isinstance(child, ast.ClassDef):
                    found.append(_span(source, name, child))
                visit(child, f"{name}.")
            else:
                visit(child, prefix)

    if tree is not None:
        visit(tree, "")
    return found


def innermost(spans: list[Span], line: int) -> str | None:
    """The name of the deepest span whose body holds `line`; None outside every span."""
    inside = [span for span in spans if span.body <= line <= span.end]
    return max(inside, key=lambda span: (span.body, -span.end)).name if inside else None


def symbol_hash(source: str, symbol: str, *, length: int = 12) -> str | None:
    """sha256 hex prefix of the symbol's source text; None when `find` finds nothing."""
    span = find(source, symbol)
    return None if span is None else hashlib.sha256(span.text.encode()).hexdigest()[:length]
