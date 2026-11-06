"""Registry fitness (blueprint W2): over a whole blueprint-suite run, every checkpoint is seen passing and not passing.

A pytest plugin records `(checkpoint id, verdict)` from every evaluation `blueprint.runner` makes, before any override
is applied, in every process (xdist workers append to one directory the controller makes). When the whole
`packages/blueprint/tests` suite has run green, each registered checkpoint and each tool role of the shipped stack
profiles must have been seen both PASSING and FAILING or NOT SET UP, except the gaps in
`packages/blueprint/tests/known_gaps.toml`. A gap names its bead; one the suite now covers must be deleted, so the
list only shrinks. A partial selection (`-k`, a node id, a test file left out) asserts nothing; the default `-m "not browser"` is not one.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pytest
    from blueprint.model import Check, Context, Sub

SUITE = Path(__file__).resolve().parent.parent / "packages" / "blueprint" / "tests"
GAPS = SUITE / "known_gaps.toml"
DIRECTIONS = ("passing", "adverse")
_BEAD = re.compile(r"shelf-[a-z0-9]+(\.[0-9]+)*")
_ENV = "SHELF_BLUEPRINT_FITNESS_DIR"
_FAMILIES = {"stack.roles", "framework.roles"}
_ADVERSE = {"failing", "not set up"}

_state: dict[str, object] = {"controller": False, "required": frozenset(), "original": None}


def direction(verdict: str) -> str | None:
    """Which side of the fitness a verdict counts for; None for the verdicts that prove nothing."""
    if verdict == "passing":
        return "passing"
    return "adverse" if verdict in _ADVERSE else None


def load_gaps(path: Path = GAPS) -> tuple[set[tuple[str, str]], list[str]]:
    """The allowed (id, direction) gaps and every problem with the file."""
    if not path.is_file():
        return set(), []
    gaps: set[tuple[str, str]] = set()
    problems: list[str] = []
    for entry in tomllib.loads(path.read_text(encoding="utf-8")).get("gap", []):
        key = (str(entry.get("id", "")), str(entry.get("direction", "")))
        if not key[0] or key[1] not in DIRECTIONS:
            problems.append(f"known gap {entry!r}: needs an id and a direction of {' or '.join(DIRECTIONS)}")
        elif not _BEAD.fullmatch(str(entry.get("bead", ""))):
            problems.append(f'known gap {key[0]} ({key[1]}): needs `bead = "shelf-..."`, the bead that closes it')
        elif key in gaps:
            problems.append(f"known gap {key[0]} ({key[1]}) is listed twice")
        gaps.add(key)
    return gaps, problems


def judge(observed: Iterable[tuple[str, str]], required: Iterable[str], gaps: set[tuple[str, str]]) -> list[str]:
    """What is wrong: a required checkpoint not seen in a direction and not allowed, a gap the suite now covers or names no checkpoint."""
    seen = {(cid, side) for cid, verdict in observed if (side := direction(verdict))}
    ids = set(required)
    problems: list[str] = []
    for cid in sorted(ids):
        problems.extend(
            f"{cid}: never seen {side} in the blueprint suite (add a scenario, or a known gap with its bead)"
            for side in DIRECTIONS
            if (cid, side) not in seen and (cid, side) not in gaps
        )
    for cid, side in sorted(gaps):
        if cid not in ids:
            problems.append(f"known gap {cid} ({side}): not a checkpoint the suite requires; delete it")
        elif (cid, side) in seen:
            problems.append(f"known gap {cid} ({side}): the suite now covers it; delete the entry")
    return problems


def _required() -> frozenset[str]:
    from blueprint.concerns.framework import FRAMEWORK_DIR  # noqa: PLC0415
    from blueprint.concerns.stack import PROFILE_DIR, load_profiles  # noqa: PLC0415
    from blueprint.model import REGISTRY  # noqa: PLC0415

    ids = {check.id for check in REGISTRY} - _FAMILIES
    for kind, directory in (("stack", PROFILE_DIR), ("framework", FRAMEWORK_DIR)):
        for name, profile in load_profiles(directory).items():
            ids.update(f"{kind}.{name}.{role}" for role, spec in profile.roles.items() if spec.tool)
    return frozenset(ids)


def _record(directory: str, subs: Iterable[Sub]) -> None:
    lines = [json.dumps([sub.id, str(sub.finding.verdict)]) for sub in subs]
    with Path(directory, f"{os.getpid()}.jsonl").open("a", encoding="utf-8") as out:
        out.write("".join(f"{line}\n" for line in lines))


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    try:
        from blueprint import runner  # noqa: PLC0415
    except ImportError:
        return
    if _ENV not in os.environ:
        os.environ[_ENV] = tempfile.mkdtemp(prefix="blueprint-fitness-")
        _state["controller"] = True
    directory = os.environ[_ENV]
    original = runner._judge  # noqa: SLF001
    _state["original"] = original

    def observed(chk: Check, ctx: Context) -> list[Sub]:
        subs = original(chk, ctx)
        _record(directory, subs)
        return subs

    runner._judge = observed  # noqa: SLF001


def _whole_suite(session: pytest.Session) -> bool:
    config = session.config
    if config.option.keyword or getattr(config.option, "deselect", None) or session.testsfailed:
        return False
    if any("::" in arg for arg in config.args):
        return False
    directory = os.environ[_ENV]
    collected = {line for path in Path(directory).glob("*.collected") for line in path.read_text(encoding="utf-8").split()}
    return bool(collected) and {p.name for p in SUITE.glob("test_*.py")} <= collected


def pytest_collection_finish(session: pytest.Session) -> None:
    """Each process notes the blueprint test files it collected: under xdist the controller collects nothing itself."""
    files = {Path(str(item.fspath)).name for item in session.items if SUITE in Path(str(item.fspath)).parents}
    directory = os.environ.get(_ENV)
    if directory is not None:
        Path(directory, f"{os.getpid()}.collected").write_text("\n".join(sorted(files)), encoding="utf-8")
    if _state["controller"]:
        _state["required"] = _required()  # before any test runs: a test's own registrations are not requirements


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    directory = os.environ.get(_ENV)
    if not _state["controller"] or directory is None:
        return
    try:
        if _state["original"] is not None:
            from blueprint import runner  # noqa: PLC0415

            runner._judge = _state["original"]  # type: ignore[assignment]  # noqa: SLF001
        if exitstatus != 0 or not _whole_suite(session):
            return
        observed = [
            tuple(json.loads(line))
            for path in Path(directory).glob("*.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        gaps, problems = load_gaps()
        problems.extend(judge(observed, _state["required"] or _required(), gaps))  # type: ignore[arg-type]
        if problems:
            session.exitstatus = 1
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            text = "blueprint registry fitness:\n  " + "\n  ".join(problems)
            if reporter is not None:
                reporter.write_line(text, red=True)
            else:
                print(text)
    finally:
        os.environ.pop(_ENV, None)
        shutil.rmtree(directory, ignore_errors=True)
