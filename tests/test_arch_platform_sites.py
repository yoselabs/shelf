"""A platform fact has one named owner; everywhere else asks for the capability (docs/platform-branches.md).

A module under `packages/*/src` may read the operating system only if it is a row below. A read is `sys.platform`,
`os.name`, `os.uname()`, `sysconfig.get_platform()`, the `platform` module's system/machine family, or an
OS-name string literal (`"darwin"`, `"linux"`, `"win32"`, `"Windows"`, `"nt"`, `"Darwin"`, `"Linux"`). Each row says
which `fact` the module decides, which module `owner` is that fact's one owner, and why. One fact, one owner: every
row of a fact names the same owner, and the owner is itself a row. A row whose module stops reading the OS leaves.
A new branch on the OS fails the gate: ask the owner, or ask for the capability (is the tool on PATH), or
list a new fact with its owner and the reason it cannot be a capability.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

from any_arch import Hit, Row, Rule, Source, check, plant

_ROOT = Path(__file__).resolve().parent.parent

_PLATFORM_CALLS = {"system", "machine", "uname", "platform", "mac_ver", "processor", "release", "version", "architecture"}
_OS_NAMES = {"darwin", "linux", "win32", "Windows", "nt", "Darwin", "Linux"}

_TABLE = "packages/stream-proc/src/stream_proc/proctable.py"
_ALLOWED: dict[str, dict[str, str]] = {
    _TABLE: {
        "fact": "process table",
        "owner": _TABLE,
        "why": "chooses the macOS libproc binding or the /proc table once at import; boot_id and inspect come from the same choice",
    },
    "packages/stream-proc/src/stream_proc/procmac.py": {
        "fact": "process table",
        "owner": _TABLE,
        "why": "the macOS native behind proctable: refuses to load the libproc dylib anywhere but darwin",
    },
    "packages/sqlite-store/src/sqlite_store/filesystem.py": {
        "fact": "mount list",
        "owner": "packages/sqlite-store/src/sqlite_store/filesystem.py",
        "why": "the fs-type probe reads /proc/mounts on linux only; elsewhere the answer is 'unknown'",
    },
    "packages/anyllm/src/anyllm/providers/claude_code_sdk.py": {
        "fact": "credential store",
        "owner": "packages/anyllm/src/anyllm/providers/claude_code_sdk.py",
        "why": "the Claude CLI keeps its OAuth session in the macOS Keychain, in a file elsewhere",
    },
    "packages/stream-proc/src/stream_proc/hold.py": {
        "fact": "rusage unit",
        "owner": "packages/stream-proc/src/stream_proc/hold.py",
        "why": "ru_maxrss is bytes on macOS, kilobytes on Linux; peak_bytes is the one conversion",
    },
}


def _reads(tree: ast.AST) -> list[int]:
    """Line numbers of every platform read in a parsed module."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and node.value in _OS_NAMES:
                lines.append(node.lineno)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            owner, attr = node.value.id, node.attr
            if (
                (owner == "sys" and attr == "platform")
                or (owner == "os" and attr in {"name", "uname"})
                or (owner == "sysconfig" and attr == "get_platform")
                or (owner == "platform" and attr in _PLATFORM_CALLS)
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module in {"platform", "sys", "sysconfig"}:
            lines += [
                node.lineno
                for alias in node.names
                if alias.name in _PLATFORM_CALLS | {"get_platform"} or (node.module == "sys" and alias.name == "platform")
            ]
    return sorted(set(lines))


def _platform_sites(source: Source) -> Iterator[Hit]:
    """Repo-relative module path and the line of each platform read in it."""
    for line in _reads(source.tree):
        yield source.rel, line


PLATFORM_SITES = Rule(
    "platform-sites",
    "platform branch outside the allowlist (one dispatch: use an owner, or list the module with a reason)",
    _platform_sites,
    {module: Row(row["why"]) for module, row in _ALLOWED.items()},
)


def test_platform_reads_stay_in_the_allowlisted_modules_and_every_row_still_reads() -> None:
    check(PLATFORM_SITES, _ROOT)


def test_every_row_names_its_fact_owner_and_reason_and_a_fact_has_one_owner() -> None:
    for module, row in _ALLOWED.items():
        assert set(row) == {"fact", "owner", "why"}, module
        assert all(text.strip() for text in row.values()), f"{module}: fact, owner and why must say something"
        owner = _ALLOWED.get(row["owner"])
        assert owner is not None, f"{module}: the owner {row['owner']} is not itself a row"
        assert owner["fact"] == row["fact"] and owner["owner"] == row["owner"], f"{module}: one fact, one owner ({row['fact']})"
        assert module.split("/src/")[0] == row["owner"].split("/src/")[0], f"{module}: the owner lives in the same package"


def _plant(tmp_path: Path, source: str) -> dict[str, list[int]]:
    return plant(PLATFORM_SITES, tmp_path, source)


def test_planted_sys_platform_read_is_found(tmp_path: Path) -> None:
    assert _plant(tmp_path, "import sys\nIS_MAC = sys.platform == 'darwin'\n") == {"packages/pkg/src/pkg/mod.py": [2]}


def test_planted_platform_module_and_os_reads_are_found(tmp_path: Path) -> None:
    source = "import os\nimport platform\na = platform.system()\nb = platform.machine()\nc = os.uname().sysname\nd = os.name\n"
    assert _plant(tmp_path, source) == {"packages/pkg/src/pkg/mod.py": [3, 4, 5, 6]}


def test_planted_from_import_is_found(tmp_path: Path) -> None:
    assert _plant(tmp_path, "from platform import system\n") == {"packages/pkg/src/pkg/mod.py": [1]}


def test_unrelated_names_pass(tmp_path: Path) -> None:
    assert _plant(tmp_path, "import sys\nplatform = 'x'\nprint(sys.argv, platform.upper())\n") == {}


def test_planted_os_name_literals_are_found(tmp_path: Path) -> None:
    source = "a = 'darwin'\nb = 'linux'\nc = 'win32'\nd = 'Windows'\ne = 'nt'\nf = 'Darwin'\ng = 'Linux'\n"
    assert _plant(tmp_path, source) == {"packages/pkg/src/pkg/mod.py": [1, 2, 3, 4, 5, 6, 7]}


def test_a_word_that_merely_contains_an_os_name_passes(tmp_path: Path) -> None:
    assert _plant(tmp_path, "a = 'linux-only'\nb = 'Is darwin here'\n") == {}
