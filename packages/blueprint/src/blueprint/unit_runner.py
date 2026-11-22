"""The runner `blueprint gate test` hands any-gate when a repo measures coverage: one unit at a time, each unit's data cached under its key.

    python -m blueprint.unit_runner --repo R --cache C --pytest-args "ARGS" PATH...

`PATH...` are the unit paths any-gate left to run. Each unit runs once, with `COVERAGE_FILE` pointing into the cache, and its data is kept
as `<unit>-<key>.cov` only when its tests passed without CLI pytest arguments. `combine` joins every unit's current key (run now or
earlier), so the floor covers the whole repo, including skipped units. Both `coverage run -m pytest` and pytest-cov are supported:
pytest-cov breaks some C
extensions' lazy import (duckdb), so a repo may need the first.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from blueprint import gate_units

KEY_LENGTH = 32
KEEP = 3  # data files kept per unit: the newest keys, so switching branches does not rerun a unit
RUN_TIMEOUT = 4 * 3600.0  # seconds one unit may take
_TOOL_TIMEOUT = 600.0


def worktree_cache(shared: Path, repo: Path) -> Path:
    """The cache of this checkout: coverage data holds absolute paths, so two worktrees never share one."""
    return shared / "".join(c if c.isalnum() else "_" for c in str(repo.resolve()))[-80:]


def data_file(cache: Path, unit: str, key: str) -> Path:
    return cache / f"{unit}-{key}.cov"


def cached(cache: Path, config: gate_units.Config, repo: Path) -> set[str]:
    """The `unit:key` of every unit whose current key has coverage data."""
    return {f"{u.name}:{k}" for u in config.units if data_file(cache, u.name, k := gate_units.key(repo, u)).is_file()}


def _command(mode: str, pytest_args: list[str], paths: tuple[str, ...]) -> list[str]:
    if mode == "pytest-cov":
        return [sys.executable, "-m", "pytest", "--cov", *pytest_args, *paths]
    return [sys.executable, "-m", "coverage", "run", "-m", "pytest", *pytest_args, *paths]


def _gather(target: Path) -> str | None:
    """Make `target` the run's one data file. `parallel = true` writes `target.<host>.<pid>.<random>` files instead: join them."""
    parts = sorted(p for p in target.parent.glob(f"{target.name}.*") if p.is_file())
    if parts:
        done = subprocess.run(
            [sys.executable, "-m", "coverage", "combine", f"--data-file={target}", *map(str, parts)], check=False, timeout=_TOOL_TIMEOUT
        )
        if done.returncode != 0:
            return "its parallel coverage data could not be combined"
    return None if target.is_file() else "wrote no coverage data"


def _prune(cache: Path, unit: str) -> None:
    files = sorted(cache.glob(f"{unit}-{'?' * KEY_LENGTH}.cov"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[KEEP:]:
        old.unlink(missing_ok=True)


def run_units(repo: Path, cache: Path, config: gate_units.Config, paths: list[str], pytest_args: list[str]) -> int:
    """Run each unit that owns one of `paths`; 0 when all passed, else the first failing exit code (the rest are not started)."""
    cache.mkdir(parents=True, exist_ok=True)
    for unit in config.units:
        todo = tuple(p for p in unit.paths if p in paths)
        if not todo:
            continue
        unit_key = gate_units.key(repo, unit)
        with tempfile.TemporaryDirectory(dir=cache) as tmp:
            target = Path(tmp) / "data"
            env = {**os.environ, **config.env, "COVERAGE_FILE": str(target)}
            command = _command(config.coverage, [*config.arguments(), *pytest_args], todo)
            done = subprocess.run(command, cwd=repo, env=env, check=False, timeout=RUN_TIMEOUT)
            if done.returncode != 0:
                return done.returncode
            if pytest_args:
                continue  # CLI selection is not proof that the unit's plain suite passed.
            if (problem := _gather(target)) is not None:
                sys.stderr.write(f"blueprint: unit {unit.name} passed but {problem} ({config.coverage}); is it installed and enabled?\n")
                return 1
            target.replace(data_file(cache, unit.name, unit_key))
        _prune(cache, unit.name)
    return 0


def combine(repo: Path, cache: Path, config: gate_units.Config) -> int:
    """Join every unit's current data and apply the floor; 0 when it holds (or no floor is set), 1 when a unit has no data or it fails."""
    files = []
    for unit in config.units:
        file = data_file(cache, unit.name, gate_units.key(repo, unit))
        if not file.is_file():
            sys.stderr.write(f"blueprint: no coverage data for unit {unit.name}: the floor cannot be judged\n")
            return 1
        files.append(str(file))
    with tempfile.TemporaryDirectory(dir=cache) as tmp:
        combined = str(Path(tmp) / "combined")
        py = [sys.executable, "-m", "coverage"]
        steps = [[*py, "combine", "--keep", f"--data-file={combined}", *files]]
        report = [*py, "report", f"--data-file={combined}"]
        if config.floor is not None:
            report.append(f"--fail-under={config.floor:g}")
        steps.append(report)
        for step in steps:
            if subprocess.run(step, cwd=repo, check=False, timeout=_TOOL_TIMEOUT).returncode != 0:
                return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blueprint.unit_runner", description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--pytest-args", default="")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    config = gate_units.load(args.repo)
    if config is None:
        sys.stderr.write("blueprint: no [tool.blueprint.test.units] in pyproject.toml\n")
        return 2
    return run_units(args.repo, args.cache, config, args.paths, shlex.split(args.pytest_args))


if __name__ == "__main__":
    sys.exit(main())
