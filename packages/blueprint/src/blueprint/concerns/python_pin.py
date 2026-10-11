"""Python and uv versions in a python-uv repo: two facts, each in one place, and CI that reads them.

`.python-version` is the interpreter every run uses (dev, CI, agents); `requires-python` is what
installers may use. They are different facts, so the check is "pin inside range", and a range that
reaches below the pin is a promise only a CI run on that lower version keeps. uv's own floor sits in
`[tool.uv] required-version`, because a different uv rewrites the lockfile's revision.
Research: openspec/changes/blueprint-skill/research/python-pin.md.
"""

from __future__ import annotations

import fnmatch
import re
import tomllib
from typing import TYPE_CHECKING

from blueprint.model import FixedBy, Sub, check_each, failing, not_set_up, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_STACK = "python-uv"
_PIN = re.compile(r"^(\d+)\.(\d+)$")
_LOWER = re.compile(r">=\s*(\d+)\.(\d+)")
_WORKFLOWS = ".github/workflows"


def _toml(ctx: Context, rel: str) -> dict[str, object]:
    text = ctx.read(rel)
    if text is None:
        return {}
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}


def _table(data: dict[str, object], *keys: str) -> dict[str, object]:
    for key in keys:
        value = data.get(key)
        data = value if isinstance(value, dict) else {}
    return data


def _ranges(ctx: Context) -> dict[str, str]:
    """`requires-python` per pyproject: the root's, and each workspace member's, by folder."""
    root = _toml(ctx, "pyproject.toml")
    found = {".": str(_table(root, "project").get("requires-python", ""))}
    members = _table(root, "tool", "uv", "workspace").get("members", [])
    patterns = [str(m) for m in members] if isinstance(members, list) else []
    for path in sorted(ctx.repo.glob("**/pyproject.toml")):
        folder = path.parent.relative_to(ctx.repo).as_posix()
        if folder != "." and any(fnmatch.fnmatch(folder, p) for p in patterns):
            found[folder] = str(_table(_toml(ctx, f"{folder}/pyproject.toml"), "project").get("requires-python", ""))
    return {folder: spec for folder, spec in found.items() if spec or folder == "."}


def _lower(spec: str) -> tuple[int, int] | None:
    match = _LOWER.search(spec)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _ci(ctx: Context) -> str:
    folder = ctx.repo / _WORKFLOWS
    return "\n".join(p.read_text(errors="replace") for p in sorted(folder.glob("*.y*ml"))) if folder.is_dir() else ""


def _pin(ctx: Context) -> tuple[tuple[int, int] | None, Finding]:
    text = ctx.read(".python-version")
    if text is None:
        return None, not_set_up("no .python-version", "uv python pin 3.12 (X.Y, the version you run); commit it", FixedBy.AUTO)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    match = _PIN.match(lines[0]) if len(lines) == 1 else None
    if match is None:
        return None, failing(
            f".python-version says {' | '.join(lines) or 'nothing'}; want one X.Y line",
            "write one line, e.g. 3.12; the lock carries the patch reproducibility",
        )
    pin = (int(match.group(1)), int(match.group(2)))
    below = [f"{folder} ({spec})" for folder, spec in _ranges(ctx).items() if (low := _lower(spec)) is not None and pin < low]
    if below:
        return pin, failing(f"pin {lines[0]} is below requires-python of {', '.join(below)}", "pin a version inside every member's range")
    return pin, passing(f".python-version {lines[0]}")


def _range(ctx: Context) -> Finding:
    ranges = _ranges(ctx)
    missing = [folder for folder, spec in ranges.items() if not spec and folder == "." and len(ranges) == 1]
    if missing:
        return not_set_up("no requires-python in pyproject.toml", 'add requires-python = ">=X.Y" under [project]')
    capped = [f"{folder} ({spec})" for folder, spec in ranges.items() if "<" in spec]
    if capped:
        return failing(
            f"upper bound on requires-python: {', '.join(capped)}", 'drop the cap: ">=X.Y" only; a cap blocks installs on new Pythons'
        )
    no_floor = [folder for folder, spec in ranges.items() if spec and _lower(spec) is None]
    if no_floor:
        return failing(f"requires-python without a >= floor: {', '.join(no_floor)}", 'write requires-python = ">=X.Y"')
    return passing("; ".join(f"{folder}: {spec}" for folder, spec in ranges.items() if spec))


def _range_tested(ctx: Context, pin: tuple[int, int] | None) -> Finding:
    if pin is None:
        return not_set_up("no usable .python-version to compare against", "fix stack.python-uv.python-pin first")
    ci = _ci(ctx)
    untested: list[str] = []
    for folder, spec in _ranges(ctx).items():
        low = _lower(spec)
        if low is not None and low < pin and not re.search(rf"\b{low[0]}\.{low[1]}\b", ci):
            untested.append(f"{folder} claims {low[0]}.{low[1]}")
    if untested:
        shown = ", ".join(untested[:5]) + (f", and {len(untested) - 5} more" if len(untested) > 5 else "")
        return failing(
            f"lower bound below the pin {pin[0]}.{pin[1]} and no CI run on it: {shown}",
            f"raise requires-python to >={pin[0]}.{pin[1]}, or add a CI job running `uv run --python <lower> make test`",
        )
    return passing(f"every lower bound is the pin {pin[0]}.{pin[1]} or has a CI run")


def _ci_python(ctx: Context) -> Finding:
    ci = _ci(ctx)
    if not ci:
        return passing(f"no {_WORKFLOWS}; nothing to read the pin")
    if "actions/setup-python" in ci:
        return failing(
            "CI installs Python with actions/setup-python, so a hard-coded version can drift from .python-version",
            "drop setup-python; setup-uv plus `uv sync` read .python-version; set python-version only on a matrix job",
        )
    return passing("CI takes Python from .python-version through uv")


def _uv_version(ctx: Context) -> Finding:
    for rel in ("uv.toml", "pyproject.toml"):
        data = _toml(ctx, rel)
        floor = (data if rel == "uv.toml" else _table(data, "tool", "uv")).get("required-version")
        if floor:
            return passing(f"{rel}: required-version {floor}")
    return not_set_up(
        "no [tool.uv] required-version", 'add [tool.uv] required-version = ">=<the uv you run>"; setup-uv reads it in CI', FixedBy.AUTO
    )


_ROWS = {
    "python-pin": ".python-version pins one X.Y, inside every requires-python range",
    "python-range": 'requires-python is ">=X.Y" everywhere, with no upper cap',
    "python-range-tested": "a lower bound below the pin is run in CI",
    "python-ci": "CI takes Python from .python-version, not a hard-coded version",
    "uv-version": "uv's version floor is declared ([tool.uv] required-version)",
}


@check_each("stack.python-pin", "python-uv repos pin Python and uv once, honestly, and CI reads the pins", layer="stack")
def python_pin(ctx: Context) -> list[Sub]:
    """Five rows under the python-uv stack."""
    if _STACK not in ctx.profile.stacks:
        return []
    pin, pin_finding = _pin(ctx)
    findings = {
        "python-pin": pin_finding,
        "python-range": _range(ctx),
        "python-range-tested": _range_tested(ctx, pin),
        "python-ci": _ci_python(ctx),
        "uv-version": _uv_version(ctx),
    }
    return [Sub(f"stack/{_STACK}", f"stack.{_STACK}.{row}", _ROWS[row], finding) for row, finding in findings.items()]
