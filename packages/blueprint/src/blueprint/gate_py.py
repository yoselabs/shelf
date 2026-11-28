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

import posixpath
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from blueprint.model import python_folder

LINT_CONFIGS = ("pyproject.toml", "ruff.toml", ".ruff.toml")
SPELL_CONFIGS = ("pyproject.toml", ".codespellrc")
_TIMEOUT = 3600.0  # seconds one tool may take


def manifest(repo: Path) -> Path:
    """The Python stack's `pyproject.toml`: the repo's own at the root, else the one in the folder below it (ADR 0034)."""
    return repo / (python_folder(repo) or ".") / "pyproject.toml"


def settings(repo: Path) -> dict[str, Any]:  # Any: parsed TOML
    try:
        data = tomllib.loads(manifest(repo).read_text(encoding="utf-8"))
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


def spell_paths(repo: Path) -> list[str]:
    """The `spell-paths` of the Python stack in `repo` (relative to its folder, where the recipe runs codespell)."""
    return _paths(repo, "spell-paths")


def lint_paths(repo: Path) -> list[str]:
    """The `lint-paths` of the Python stack in `repo` (relative to its folder, where the recipe runs ruff)."""
    return _paths(repo, "lint-paths")


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


def norm(path: str) -> str:
    """A `lint-paths` entry as a repo-relative POSIX path: `./src`, `src/` and `src//` are `src`; the root (`.`, `./`, empty) is `""`."""
    clean = posixpath.normpath(path.strip() or ".")
    return "" if clean == "." else clean.removeprefix("./")


def under(path: str, roots: list[str]) -> bool:
    """Whether `path` is inside a `lint-paths` entry (a folder holds what is below it, a file is itself); no entries means the whole repo.

    The one reading shared by `lint-changed`'s globs, the commit hook and the `gate.lint-paths-cover-python` row.
    """
    if not roots:
        return True
    return any(not r or path == r or path.startswith(f"{r}/") for r in map(norm, roots))


def _globs(repo: Path, paths: list[str], suffix: str) -> list[str]:
    """`any_gate changed` patterns for `paths`: a folder is everything below it (with `suffix`), a file is itself."""
    if not paths:
        return [f"*{suffix}"]
    globs = []
    for raw in paths:
        p = norm(raw)
        globs.append(f"{p}/*{suffix}" if p and (repo / p).is_dir() else p or f"*{suffix}")
    return globs


def _anchor(repo: Path) -> tuple[Path, str]:
    """The git top level `repo` sits in, and `repo`'s folder below it as a prefix (`backend/`; empty at the top).

    `any_gate changed` reports git-root paths for tracked changes and folder-relative ones for untracked files, so a folder below the
    top is asked through the top, never through itself: asked from `backend/` it would find nothing and report "no file changed".
    """
    if (repo / ".git").exists():
        return repo, ""
    done = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repo, capture_output=True, text=True, check=False, timeout=60)
    top = Path(done.stdout.strip()).resolve() if done.returncode == 0 and done.stdout.strip() else repo
    here = repo.resolve()
    return (top, "") if top == here or top not in here.parents else (top, f"{here.relative_to(top).as_posix()}/")


def changed(repo: Path, globs: list[str], configs: tuple[str, ...], *, scope: str) -> list[str] | None:
    """The files to check (paths relative to `repo`), or None when git or any_gate failed (the caller then checks everything)."""
    top, prefix = _anchor(repo)
    cmd = [sys.executable, "-m", "any_gate", "changed", "--scope", scope]
    for config in configs:
        if (repo / config).is_file():
            cmd += ["--config", f"{prefix}{config}"]
    done = subprocess.run(cmd + [f"{prefix}{g}" for g in globs], cwd=top, capture_output=True, check=False, timeout=_TIMEOUT)
    if done.returncode != 0:
        return None
    return [f.removeprefix(prefix) for f in done.stdout.decode().split("\0") if f and f.startswith(prefix)]


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
