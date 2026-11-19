"""One place configures an httpx client: bare `httpx.Client(` / `httpx.AsyncClient(` is built only by
mcp-call and mcp-feedback source (each states timeout, redirect policy and a body policy) plus the test
files below, which talk to a local server. Anything else (a new package, a script) goes through http-fetch
(curl_cffi, capped body) or joins the list with a reason, so a client never ships with httpx's defaults:
no overall timeout budget, redirects unchecked, body unbounded.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = _ROOT / "packages"
_CLIENTS = {"Client", "AsyncClient"}

_SOURCE_OWNERS = ("mcp-call/src/", "mcp-feedback/src/")
_TEST_FILES = {
    "async-scope/tests/test_asgi.py": "legitimate: drives serve_asgi over a local socket",
    "asgi-token-gate/tests/test_asgi_token_gate.py": "legitimate: in-process ASGI transport",
}


def _imports_httpx_names(tree: ast.Module) -> set[str]:
    return {
        a.asname or a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module == "httpx"
        for a in n.names
        if a.name in _CLIENTS
    }


def bare_client_files(packages: Path) -> set[str]:
    """Relative paths (`pkg/src/...`, `pkg/tests/...`) of files that call an httpx client constructor."""
    found: set[str] = set()
    for path in sorted(packages.glob("*/**/*.py")):
        rel = path.relative_to(packages).as_posix()
        if "/src/" not in rel and "/tests/" not in rel:
            continue
        tree = ast.parse(path.read_text())
        direct = _imports_httpx_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute) and func.attr in _CLIENTS and isinstance(func.value, ast.Name) and func.value.id == "httpx"
            ) or (isinstance(func, ast.Name) and func.id in direct):
                found.add(rel)
    return found


def _violations(packages: Path) -> set[str]:
    return {rel for rel in bare_client_files(packages) if not rel.startswith(_SOURCE_OWNERS) and rel not in _TEST_FILES}


def test_bare_httpx_clients_live_only_in_the_two_owners_and_listed_tests() -> None:
    assert _violations(_PACKAGES) == set(), "a bare httpx client outside mcp-call/mcp-feedback: use http-fetch or state why here"


def test_every_listed_test_file_still_builds_a_client() -> None:
    stale = set(_TEST_FILES) - bare_client_files(_PACKAGES)
    assert stale == set(), f"no longer builds an httpx client: delete its entry: {sorted(stale)}"


def test_every_listed_test_file_says_why() -> None:
    assert all(reason.startswith("legitimate: ") for reason in _TEST_FILES.values())


def test_the_two_owners_do_build_a_client() -> None:
    built = bare_client_files(_PACKAGES)
    for owner in _SOURCE_OWNERS:
        assert any(rel.startswith(owner) for rel in built), f"{owner} no longer builds a client: drop it from _SOURCE_OWNERS"


def _plant(tmp_path: Path, rel: str, source: str) -> set[str]:
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text(source)
    return _violations(tmp_path)


def test_planted_module_attribute_client_fails(tmp_path: Path) -> None:
    assert _plant(tmp_path, "pkg/src/pkg/m.py", "import httpx\nc = httpx.Client()\n") == {"pkg/src/pkg/m.py"}


def test_planted_from_import_async_client_fails(tmp_path: Path) -> None:
    assert _plant(tmp_path, "pkg/src/pkg/m.py", "from httpx import AsyncClient as A\nc = A(timeout=1)\n") == {"pkg/src/pkg/m.py"}


def test_planted_client_in_an_owner_passes(tmp_path: Path) -> None:
    assert _plant(tmp_path, "mcp-call/src/mcp_call/m.py", "import httpx\nc = httpx.Client()\n") == set()


def test_a_client_named_in_a_string_or_unrelated_call_passes(tmp_path: Path) -> None:
    source = 'import httpx\nX = "httpx.Client()"\ndef f(client: httpx.Client) -> None:\n    other.Client()\n'
    assert _plant(tmp_path, "pkg/src/pkg/m.py", source) == set()
