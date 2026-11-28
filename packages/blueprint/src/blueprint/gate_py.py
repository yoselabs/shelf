"""The python stack's gate steps as engine commands, so a repo's justfile defines none of them: `lint`, `format`, `spell`.

What a repo may differ in is data, in `pyproject.toml`, never a replacement recipe (ADR 0033):

    [tool.blueprint.gate]
    lint-paths = ["packages", "tests", "tools", "conftest.py"]   # what ruff reads; default: the repo root
    spell-paths = ["packages", "docs", "README.md"]               # what codespell reads; default: its own default
    steps = ["arch", "tag-check"]                                  # more steps after the rendered ones (recipes the repo defines)

`--changed` (the per-commit gate) lints only the files changed against the base through `any_gate changed`: a changed config file, or no
base, selects everything. `test-all` is `blueprint gate test` over every suite (`gate_test`): one runner, one queue for the test slot.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

LINT_CONFIGS = ("pyproject.toml", "ruff.toml", ".ruff.toml")
SPELL_CONFIGS = ("pyproject.toml", ".codespellrc")
_TIMEOUT = 3600.0  # seconds one tool may take


def settings(repo: Path) -> dict[str, Any]:  # Any: parsed TOML
    try:
        data = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    table = data.get("tool", {}).get("blueprint", {})
    return {
        "gate": table.get("gate", {}),
        "test": table.get("test", {}),
        "coverage-report": data.get("tool", {}).get("coverage", {}).get("report", {}),
    }


def _paths(repo: Path, key: str) -> list[str]:
    raw: object = settings(repo).get("gate", {}).get(key, [])
    return [str(p) for p in raw] if isinstance(raw, list) else []


def extra_steps(repo: Path) -> tuple[str, ...]:
    """The steps `[tool.blueprint.gate] steps` adds to `check`, in order."""
    return tuple(_paths(repo, "steps"))


def generated(repo: Path) -> list[dict[str, Any]]:  # Any: parsed TOML
    """The `[[tool.blueprint.gate.generated]]` entries that name a generator, a command with `{out}` and outputs."""
    raw: object = settings(repo).get("gate", {}).get("generated", [])
    entries: list[Any] = raw if isinstance(raw, list) else []
    return [e for e in entries if isinstance(e, dict) and e.get("name") and "{out}" in str(e.get("command", "")) and e.get("outputs")]


def release_gate(repo: Path) -> bool:
    """Only an explicit boolean opts a repo into rendering the release gate."""
    gate = settings(repo).get("gate", {})
    return isinstance(gate, dict) and gate.get("release-gate") is True


def _globs(repo: Path, paths: list[str], suffix: str) -> list[str]:
    """`any_gate changed` patterns for `paths`: a folder is everything below it (with `suffix`), a file is itself."""
    if not paths:
        return [f"*{suffix}"]
    return [f"{p}/*{suffix}" if (repo / p).is_dir() else p for p in paths]


def changed(repo: Path, globs: list[str], configs: tuple[str, ...], *, scope: str) -> list[str] | None:
    """The files to check, or None when git or any_gate failed (the caller then checks everything)."""
    cmd = [sys.executable, "-m", "any_gate", "changed", "--scope", scope]
    for config in configs:
        if (repo / config).is_file():
            cmd += ["--config", config]
    done = subprocess.run(cmd + globs, cwd=repo, capture_output=True, check=False, timeout=_TIMEOUT)
    if done.returncode != 0:
        return None
    return [f for f in done.stdout.decode().split("\0") if f]


def _call(cmd: list[str], repo: Path) -> int:
    return subprocess.run(cmd, cwd=repo, check=False, timeout=_TIMEOUT).returncode


def lint(repo: Path) -> int:
    """Every declared path: ruff, then codespell (one gate step for the per-file linters)."""
    linted, spelled = _run_lint(repo, only_changed=False), _run_spell(repo, only_changed=False)
    return linted or spelled


def lint_changed(repo: Path) -> int:
    """Only the files changed against the base, by ruff and by codespell; everything when none can be told."""
    linted, spelled = _run_lint(repo, only_changed=True), _run_spell(repo, only_changed=True)
    return linted or spelled


def _run_lint(repo: Path, *, only_changed: bool) -> int:
    paths = _paths(repo, "lint-paths") or ["."]
    targets = paths
    if only_changed:
        files = changed(repo, _globs(repo, _paths(repo, "lint-paths"), ".py"), LINT_CONFIGS, scope="changed")
        if files is not None:
            if not files:
                sys.stdout.write("skipped lint: no Python file changed\n")
                return 0
            targets = files
    sys.stdout.write(f"gate-note: {len(targets)} {'files' if only_changed else 'paths'}\n")  # the gate's step line shows it (any_gate.note)
    ruff = [sys.executable, "-m", "ruff"]
    check = [*ruff, "check", *(["--force-exclude"] if only_changed else []), *targets]
    form = [*ruff, "format", "--check", *(["--force-exclude"] if only_changed else []), *targets]
    checked, formatted = _call(check, repo), _call(form, repo)
    return checked or formatted


def format_(repo: Path) -> int:
    return _call([sys.executable, "-m", "ruff", "format", *(_paths(repo, "lint-paths") or ["."])], repo)


def spell(repo: Path) -> int:
    """Every declared path."""
    return _run_spell(repo, only_changed=False)


def spell_changed(repo: Path) -> int:
    """Only the files changed against the base; everything when none can be told."""
    return _run_spell(repo, only_changed=True)


def _run_spell(repo: Path, *, only_changed: bool) -> int:
    paths = _paths(repo, "spell-paths")
    targets = paths
    if only_changed:
        files = changed(repo, _globs(repo, paths, ""), SPELL_CONFIGS, scope="changed")
        if files is not None:
            if not files:
                sys.stdout.write("skipped spell: no file changed\n")
                return 0
            targets = files
    return _call([sys.executable, "-m", "codespell_lib", *targets], repo)
