"""Python and uv versions in a python-uv repo: two facts, each in one place, and images that read them.

`.python-version` is the interpreter every run uses (dev, agents); `requires-python` is what
installers may use. They are different facts, so the check is "pin inside range". uv's own floor sits in
`[tool.uv] required-version`, because a different uv rewrites the lockfile's revision.
Research: docs/research/blueprint-skill/research/python-pin.md.
"""

from __future__ import annotations

import fnmatch
import re
from typing import TYPE_CHECKING

from blueprint.model import FixedBy, Sub, check_each, dockerfiles, failing, not_set_up, passing, toml_table

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_STACK = "python-uv"
_PIN = re.compile(r"^(\d+)\.(\d+)$")
_LOWER = re.compile(r">=\s*(\d+)\.(\d+)")
_UV_IMAGE = re.compile(r"--from=ghcr\.io/astral-sh/uv(?::([^\s@/]+))?")
_EXACT_FLOOR = re.compile(r"^==\s*(\d+\.\d+\.\d+)$")


def _ranges(ctx: Context) -> dict[str, str]:
    """`requires-python` per pyproject: the root's, and each workspace member's, by folder."""
    root = ctx.toml("pyproject.toml")
    found = {".": str(toml_table(root, "project").get("requires-python", ""))}
    members = toml_table(root, "tool", "uv", "workspace").get("members", [])
    patterns: list[str] = [str(m) for m in members] if isinstance(members, list) else []
    for path in sorted(ctx.repo.glob("**/pyproject.toml")):
        folder = path.parent.relative_to(ctx.repo).as_posix()
        if folder != "." and any(fnmatch.fnmatch(folder, p) for p in patterns):
            found[folder] = str(toml_table(ctx.toml(f"{folder}/pyproject.toml"), "project").get("requires-python", ""))
    return {folder: spec for folder, spec in found.items() if spec or folder == "."}


def _lower(spec: str) -> tuple[int, int] | None:
    match = _LOWER.search(spec)
    return (int(match.group(1)), int(match.group(2))) if match else None


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


def _uv_version(ctx: Context) -> Finding:
    for rel in ("uv.toml", "pyproject.toml"):
        data = ctx.toml(rel)
        floor = (data if rel == "uv.toml" else toml_table(data, "tool", "uv")).get("required-version")
        if floor:
            return passing(f"{rel}: required-version {floor}")
    return not_set_up(
        "no [tool.uv] required-version",
        'add [tool.uv] required-version = ">=<the uv you run>"',
        FixedBy.AUTO,
    )


def _uv_pin(ctx: Context) -> tuple[str, str] | None:
    """The one uv version the repo runs, with where it is pinned: mise.toml (ADR 0024), else an exact required-version."""
    spec = toml_table(ctx.toml("mise.toml"), "tools").get("uv")
    version = str(spec.get("version", "")) if isinstance(spec, dict) else str(spec or "")
    if re.match(r"^\d+\.\d+\.\d+$", version):
        return version, "mise.toml"
    exact = _EXACT_FLOOR.match(str(_floor(ctx) or "").strip())
    return (exact.group(1), "required-version") if exact else None


def _floor(ctx: Context) -> object:
    for rel in ("uv.toml", "pyproject.toml"):
        data = ctx.toml(rel)
        if floor := (data if rel == "uv.toml" else toml_table(data, "tool", "uv")).get("required-version"):
            return floor
    return None


def _uv_images(ctx: Context) -> Finding:
    copies = [p for p in dockerfiles(ctx.repo, ctx.profile.ignore) if _UV_IMAGE.search(p.read_text(errors="replace"))]
    if not copies:
        return passing("no image copies uv")
    pinned = _uv_pin(ctx)
    if pinned is None:
        return not_set_up(
            "an image installs uv, and no exact uv pin to compare it with", 'pin uv exactly in mise.toml (`uv = "X.Y.Z"`, ADR 0024)'
        )
    pin, where = pinned
    problems: list[str] = []
    for p in copies:
        tags = {m.group(1) or "no tag" for m in _UV_IMAGE.finditer(p.read_text(errors="replace"))}
        problems += [f"{p.relative_to(ctx.repo).as_posix()} copies uv:{tag}, the pin is {pin}" for tag in sorted(tags) if tag != pin]
    if problems:
        return failing("; ".join(problems), f"install uv {pin} ({where}) in every image: `COPY --from=ghcr.io/astral-sh/uv:{pin}`")
    return passing(f"images install uv {pin}, the {where} pin")


_ROWS = {
    "python-pin": ".python-version pins one X.Y, inside every requires-python range",
    "python-range": 'requires-python is ">=X.Y" everywhere, with no upper cap',
    "uv-version": "uv's version floor is declared ([tool.uv] required-version)",
    "uv-images": "container images install the pinned uv, not the newest",
}


@check_each("stack.python-pin", "python-uv repos pin Python and uv once, honestly, and images read the pins", layer="stack")
def python_pin(ctx: Context) -> list[Sub]:
    """Four rows under the python-uv stack."""
    if _STACK not in ctx.profile.stacks:
        return []
    pin_finding = _pin(ctx)[1]
    findings = {
        "python-pin": pin_finding,
        "python-range": _range(ctx),
        "uv-version": _uv_version(ctx),
        "uv-images": _uv_images(ctx),
    }
    return [Sub(f"stack/{_STACK}", f"stack.{_STACK}.{row}", _ROWS[row], finding) for row, finding in findings.items()]
