"""Platform branches live in a short allowlist of modules, each with a reason (Article III, one dispatch).

Reads of `sys.platform`, `os.name`, `os.uname()`, `sysconfig.get_platform()` and the `platform` module's
system/machine/uname family in `packages/*/src` are allowed only in the modules listed below. A new
branch on the operating system fails the gate: route it through one of the listed owners, or add the
module here with the reason it must decide for itself. A listed module that stops reading the platform
must leave the list.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_PLATFORM_CALLS = {"system", "machine", "uname", "platform", "mac_ver", "processor", "release", "version", "architecture"}

_ALLOWED: dict[str, str] = {
    "packages/stream-proc/src/stream_proc/owned.py": "boot_id per OS (sysctl darwin, /proc linux); inspect_process picks procmac or procfs",
    "packages/stream-proc/src/stream_proc/proctable.py": "chooses the darwin libproc binding or the portable table once at import",
    "packages/stream-proc/src/stream_proc/procmac.py": "guards the libproc dylib: refuses to load anywhere but darwin",
    "packages/sqlite-store/src/sqlite_store/filesystem.py": "fs-type probe reads /proc/mounts on linux only; others report unknown",
    "packages/anyllm/src/anyllm/providers/claude_code_sdk.py": "claude.exe name on Windows; darwin-only keychain credential probe",
    "packages/any-agent/src/any_agent/harnesses/opencode.py": "reports whether the command sandbox exists: sandbox-exec is darwin only",
    "packages/any-speech/src/any_speech/adapters/_child.py": "ru_maxrss unit differs: bytes on darwin, kilobytes on linux",
}


def _reads(tree: ast.AST) -> list[int]:
    """Line numbers of every platform read in a parsed module."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
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
    return sorted(lines)


def platform_sites(root: Path) -> dict[str, list[int]]:
    """Repo-relative module path -> lines that read the platform, for `root/packages/*/src`."""
    sites: dict[str, list[int]] = {}
    for path in sorted((root / "packages").glob("*/src/**/*.py")):
        if lines := _reads(ast.parse(path.read_text())):
            sites[path.relative_to(root).as_posix()] = lines
    return sites


def test_platform_reads_stay_in_the_allowlisted_modules() -> None:
    stray = {module: lines for module, lines in platform_sites(_ROOT).items() if module not in _ALLOWED}
    assert not stray, f"platform branch outside the allowlist (one dispatch: use an owner, or list the module with a reason): {stray}"


def test_every_allowlisted_module_still_reads_the_platform_and_says_why() -> None:
    sites = platform_sites(_ROOT)
    assert not sorted(set(_ALLOWED) - set(sites)), "an allowlisted module no longer reads the platform: delete its row"
    assert all(reason.strip() for reason in _ALLOWED.values())


def _plant(tmp_path: Path, source: str) -> dict[str, list[int]]:
    module = tmp_path / "packages" / "pkg" / "src" / "pkg" / "mod.py"
    module.parent.mkdir(parents=True)
    module.write_text(source)
    return platform_sites(tmp_path)


def test_planted_sys_platform_read_is_found(tmp_path: Path) -> None:
    assert _plant(tmp_path, "import sys\nIS_MAC = sys.platform == 'darwin'\n") == {"packages/pkg/src/pkg/mod.py": [2]}


def test_planted_platform_module_and_os_reads_are_found(tmp_path: Path) -> None:
    source = "import os\nimport platform\na = platform.system()\nb = platform.machine()\nc = os.uname().sysname\nd = os.name\n"
    assert _plant(tmp_path, source) == {"packages/pkg/src/pkg/mod.py": [3, 4, 5, 6]}


def test_planted_from_import_is_found(tmp_path: Path) -> None:
    assert _plant(tmp_path, "from platform import system\n") == {"packages/pkg/src/pkg/mod.py": [1]}


def test_unrelated_names_pass(tmp_path: Path) -> None:
    assert _plant(tmp_path, "import sys\nplatform = 'x'\nprint(sys.argv, platform.upper())\n") == {}
