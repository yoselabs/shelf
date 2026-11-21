"""Constitution II as a check: libraries take ``env: Mapping``, only the edge reads the process environment.

``os.environ`` / ``os.getenv`` / ``os.putenv`` / ``os.unsetenv`` and ``Path.home()`` are read in packages' ``src`` only in:
a ``__main__.py``, a ``cli.py`` / ``cli_*.py`` module, and the two owner packages ``settings-base`` and ``app-dirs``.
Every other file that reads them is a recorded row in ``_ALLOWLIST`` below with a one-line reason.
A stale entry (the file no longer reads the environment) fails too, so the list can only shrink.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = _ROOT / "packages"

_OWNER_PACKAGES = frozenset({"settings-base", "app-dirs"})
_OS_NAMES = frozenset({"environ", "getenv", "putenv", "unsetenv"})

# path (relative to packages/) -> reason. Recorded rows: blueprint is a stdlib-only engine whose Context default and
# self-location probe sit at its public entry, and its testing double builds a developer-shaped PATH. Not debts of a
# library function that should take `env`; revisit if blueprint grows a real caller-supplied env at every entry.
_ALLOWLIST = {
    "blueprint/src/blueprint/model.py": "Context.env defaults to dict(os.environ): the stdlib-only engine's one entry default",
    "blueprint/src/blueprint/report.py": "engine() probes the shelf checkout blueprint itself runs from (cached, no caller env exists)",
    "blueprint/src/blueprint/testing.py": "test double builds its PATH from os.environ",
}


def _is_edge(path: Path) -> bool:
    rel = path.relative_to(_PACKAGES)
    return rel.parts[0] in _OWNER_PACKAGES or path.name in {"__main__.py", "cli.py"} or path.name.startswith("cli_")


def _reads_in(source: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id == "os" and node.attr in _OS_NAMES:
                hits.append((node.lineno, f"os.{node.attr}"))
            elif node.attr == "home" and (getattr(base, "id", None) == "Path" or getattr(base, "attr", None) == "Path"):
                hits.append((node.lineno, "Path.home"))
        elif isinstance(node, ast.ImportFrom) and node.module == "os" and any(a.name in _OS_NAMES for a in node.names):
            hits.append((node.lineno, "from os import " + ", ".join(a.name for a in node.names if a.name in _OS_NAMES)))
    return hits


def _reads(path: Path) -> list[tuple[int, str]]:
    return _reads_in(path.read_text(encoding="utf-8"))


def _readers() -> dict[str, list[tuple[int, str]]]:
    found = {}
    for path in sorted(_PACKAGES.glob("*/src/**/*.py")):
        if hits := _reads(path):
            found[path.relative_to(_PACKAGES).as_posix()] = hits
    return found


def test_only_the_edge_reads_the_process_environment() -> None:
    offenders = {rel: hits for rel, hits in _readers().items() if not _is_edge(_PACKAGES / rel) and rel not in _ALLOWLIST}
    assert not offenders, (
        "os.environ / os.getenv / Path.home() belong to __main__, cli modules, settings-base and app-dirs; "
        f"take `env: Mapping[str, str]` (and `home: Path`) instead: {offenders}"
    )


def test_the_allowlist_has_no_stale_entries() -> None:
    readers = {rel for rel in _readers() if not _is_edge(_PACKAGES / rel)}
    stale = sorted(set(_ALLOWLIST) - readers)
    assert not stale, f"no longer read the environment, remove them from _ALLOWLIST: {stale}"


def test_every_allowlist_entry_says_why() -> None:
    blank = sorted(rel for rel, reason in _ALLOWLIST.items() if not reason.strip())
    assert not blank, f"each allowlisted file needs a one-line reason: {blank}"


def test_the_detector_sees_every_read_shape() -> None:
    for src in (
        "os.environ",
        "os.environ.get('A')",
        "os.getenv('A')",
        "os.putenv('A', '1')",
        "os.unsetenv('A')",
        "from os import environ",
        "from os import getenv as g",
        "Path.home()",
        "pathlib.Path.home()",
    ):
        assert _reads_in(src), src
    for src in ("env.get('A')", "home / '.config'", "os.pathsep", "os.path.join(a, b)", "Path(home)", "from os import path"):
        assert not _reads_in(src), src


def test_the_edge_is_main_cli_and_the_two_owners() -> None:
    edge = ("a/src/a/__main__.py", "a/src/a/cli.py", "a/src/a/cli_run.py", "settings-base/src/x.py", "app-dirs/src/x.py")
    for rel in edge:
        assert _is_edge(_PACKAGES / rel), rel
    for rel in ("a/src/a/core.py", "a/src/a/client.py", "child-env/src/child_env/__init__.py"):
        assert not _is_edge(_PACKAGES / rel), rel
