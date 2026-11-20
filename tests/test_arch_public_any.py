"""A public signature carries a contract, not `Any` (docs/agents/python.md: no `Any` without a one-line reason).

Neither pyrefly (strict has no explicit-Any error) nor ruff (ANN401 sees only a bare `Any`, never
`dict[str, Any]` or `Callable[..., Any]`, and flags private functions too) can say this, so the walk is here.

What it checks: in a package that opted in, every public function, method and dataclass field whose
annotation names `Any` carries a `# Any: <reason>` comment on its signature lines (the field's line).
Public = no leading underscore on the module, class or function (dunders count); nested functions are not API.
What it does not check: `object`-typed holes, `cast`, `# type: ignore`, module-level aliases, a reason's quality.

A package opts in by name under `[tool.shelf-public-any]` in the root pyproject: add it once it passes, never to
count violations. A package that has not opted in is not checked.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_REASON = "# Any:"


def _names_any(node: ast.expr | None) -> bool:
    if node is None:
        return False
    return any((isinstance(n, ast.Name) and n.id == "Any") or (isinstance(n, ast.Attribute) and n.attr == "Any") for n in ast.walk(node))


def _is_public(name: str) -> bool:
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def public_any(source: str) -> list[str]:
    """`line name` of every public signature that names `Any` without a `# Any:` reason on its lines."""
    lines = source.splitlines()
    found: list[str] = []

    def walk(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _is_public(node.name):
                a = node.args
                annotated = [x.annotation for x in (*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg) if x is not None]
                signature = lines[node.lineno - 1 : node.body[0].lineno - 1 or node.lineno]
                if any(_names_any(x) for x in (*annotated, node.returns)) and not any(_REASON in ln for ln in signature):
                    found.append(f"{node.lineno} {node.name}")
            elif isinstance(node, ast.ClassDef) and _is_public(node.name):
                walk(node.body)
                found.extend(
                    f"{m.lineno} {ast.unparse(m.target)}"
                    for m in node.body
                    if isinstance(m, ast.AnnAssign) and _names_any(m.annotation) and _REASON not in lines[m.lineno - 1]
                )

    walk(ast.parse(source).body)
    return found


def _opted_in() -> list[str]:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return list(config["tool"]["shelf-public-any"]["packages"])


def _public_sources(package: str) -> list[Path]:
    src = _ROOT / "packages" / package / "src"
    return [
        p for p in src.rglob("*.py") if not any(part.startswith("_") and part != "__init__.py" for part in p.relative_to(src).parts[1:])
    ]


def test_an_opted_in_package_names_no_any_in_a_public_signature_without_a_reason() -> None:
    packages = _opted_in()
    assert packages, "no package opted in; the walk is vacuous"
    offenders = {
        f"{p.relative_to(_ROOT)}:{hit}": None
        for package in packages
        for p in _public_sources(package)
        for hit in public_any(p.read_text(encoding="utf-8"))
    }
    assert not offenders, (
        "`Any` in a public signature: type it (a frozen dataclass or TypedDict for a dict) or add a `# Any: <reason>` comment on it:\n  "
        + "\n  ".join(offenders)
    )


def test_every_opted_in_name_is_a_package() -> None:
    assert all((_ROOT / "packages" / name / "src").is_dir() for name in _opted_in())


def test_the_rule_flags_the_shapes_it_exists_for() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "from typing import Any\n"
        "def a(x: dict[str, Any]) -> int: ...\n"
        "def b() -> Any: ...\n"
        "def c(*args: Any) -> None: ...\n"
        "class K:\n"
        "    def d(self, f: Callable[..., Any]) -> None: ...\n"
        "@dataclass\n"
        "class D:\n"
        "    raw: dict[str, Any]\n"
    )
    assert [hit.split()[1] for hit in public_any(source)] == ["a", "b", "c", "d", "raw"]


def test_the_rule_lets_through_a_reason_a_private_name_and_a_typed_signature() -> None:
    source = (
        "from typing import Any\n"
        "def a(x: dict[str, Any]) -> int:  # Any: parsed JSON, checked below\n"
        "    return 1\n"
        "def b(\n"
        "    x: Any,  # Any: the caller's own type\n"
        ") -> int:\n"
        "    return 1\n"
        "def _c(x: Any) -> Any: ...\n"
        "class _K:\n"
        "    def d(self, x: Any) -> None: ...\n"
        "class D:\n"
        "    raw: dict[str, Any]  # Any: a pass-through\n"
        "    def e(self, x: int) -> str:\n"
        "        def inner(y: Any) -> Any: ...\n"
        "        return ''\n"
    )
    assert public_any(source) == []
