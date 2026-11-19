"""Constitution II as a check: libraries take ``env: Mapping``, only the edge reads the process environment.

``os.environ`` / ``os.getenv`` / ``os.putenv`` / ``os.unsetenv`` and ``Path.home()`` are read in packages' ``src`` only in:
a ``__main__.py``, a ``cli.py`` / ``cli_*.py`` module, and the two owner packages ``settings-base`` and ``app-dirs``.
Every other file that reads them is listed in ``_ALLOWLIST`` below with a one-line reason; the consumer wave empties it.
A stale entry (the file no longer reads the environment) fails too, so the list can only shrink.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = _ROOT / "packages"

_OWNER_PACKAGES = frozenset({"settings-base", "app-dirs"})
_OS_NAMES = frozenset({"environ", "getenv", "putenv", "unsetenv"})

# path (relative to packages/) -> reason. Consumer wave empties this (shelf-tyld.6, feeds shelf-ufmg).
_ALLOWLIST = {
    "any-agent/src/any_agent/procs.py": "reads ANY_AGENT_STOP_GRACE at import time into GRACE_S",
    "any-agent/src/any_agent/harnesses/codex.py": "CODEX_HOME / ~/.codex session folder (app-dirs.tool_home)",
    "any-agent/src/any_agent/harnesses/claude.py": "~/.claude/projects transcript lookup (app-dirs.tool_home)",
    "any-agent/src/any_agent/harnesses/opencode.py": "XDG_DATA_HOME / ~/.local/share log + auth.json, ~/.opencode/bin (app-dirs.data_dir)",
    "any-agent/src/any_agent/harnesses/opencode_sandbox.py": "reads home and XDG_CONFIG_HOME for the sandbox deny list",
    "any-browser/src/any_browser/zendriver.py": "reads the executable and Playwright path variables to find the browser",
    "any-recorded-fixture/src/any_recorded_fixture/__init__.py": "default argument env=os.environ for update_requested",
    "any-speech/src/any_speech/defaults.py": "falls back to os.environ and Path.home() when env/home are not passed",
    "anyembed/src/anyembed/local.py": "MUTATES os.environ (setdefault HF_HUB_OFFLINE, TRANSFORMERS_OFFLINE)",
    "anyllm/src/anyllm/providers/claude_code_cli.py": "passes dict(os.environ) to the child process",
    "anyllm/src/anyllm/providers/anthropic_api.py": "reads the API key variable at call time",
    "anyllm/src/anyllm/providers/openai_compatible.py": "reads the API key variable at call time",
    "anyllm/src/anyllm/providers/codex_cli.py": "filters os.environ into the child process environment",
    "anyllm/src/anyllm/providers/claude_code_sdk.py": "reads the OAuth token variable at call time",
    "blueprint/src/blueprint/concerns/gate_clone.py": "~/.config/mise path from Path.home()",
    "blueprint/src/blueprint/model.py": "Context.env defaults to dict(os.environ)",
    "blueprint/src/blueprint/recipes/gate_state.py": "standalone copied recipe: GATE_LOCK_FILE, XDG_CACHE_HOME, child env",
    "blueprint/src/blueprint/report.py": "passes os.environ (minus git location) to a git child",
    "blueprint/src/blueprint/testing.py": "test double builds PATH from os.environ",
    "git-porcelain/src/git_porcelain/porcelain.py": "filters os.environ for git children and reads GIT_DIR",
    "git-porcelain/src/git_porcelain/real_env.py": "default source for the git child environment is os.environ",
    "launchd-agent/src/launchd_agent/__init__.py": "LaunchAgents folder under Path.home()",
    "stream-proc/src/stream_proc/registered.py": "falls back to os.environ for the child environment",
    "child-env/src/child_env/__init__.py": "scrub_current() reads os.environ (callers should pass the mapping to scrub)",
}


def _is_edge(path: Path) -> bool:
    rel = path.relative_to(_PACKAGES)
    return rel.parts[0] in _OWNER_PACKAGES or path.name in {"__main__.py", "cli.py"} or path.name.startswith("cli_")


def _reads(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id == "os" and node.attr in _OS_NAMES:
                hits.append((node.lineno, f"os.{node.attr}"))
            elif node.attr == "home" and (getattr(base, "id", None) == "Path" or getattr(base, "attr", None) == "Path"):
                hits.append((node.lineno, "Path.home"))
        elif isinstance(node, ast.ImportFrom) and node.module == "os" and any(a.name in _OS_NAMES for a in node.names):
            hits.append((node.lineno, "from os import " + ", ".join(a.name for a in node.names if a.name in _OS_NAMES)))
    return hits


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
