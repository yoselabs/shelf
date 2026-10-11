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
from typing import TYPE_CHECKING

from blueprint.model import FixedBy, Sub, check_each, dockerfiles, failing, not_set_up, passing, toml_table

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_STACK = "python-uv"
_PIN = re.compile(r"^(\d+)\.(\d+)$")
_LOWER = re.compile(r">=\s*(\d+)\.(\d+)")
_WORKFLOWS = ".github/workflows"
# The first setup-uv that reads `required-version` when its `version:` input is omitted (README bisected per tag, 2026-10-11).
_SETUP_UV_READS_FLOOR = (5, 2, 0)
_SETUP_UV = re.compile(r"uses:\s*astral-sh/setup-uv@(\S+)(?:\s*#\s*(\S+))?")
_STEP_VERSION = re.compile(r"^\s*version:\s*[\"']?([^\"'\s#]+)")
_UV_IMAGE = re.compile(r"--from=ghcr\.io/astral-sh/uv(?::([^\s@/]+))?")
_EXACT_FLOOR = re.compile(r"^==\s*(\d+\.\d+\.\d+)$")


def _ranges(ctx: Context) -> dict[str, str]:
    """`requires-python` per pyproject: the root's, and each workspace member's, by folder."""
    root = ctx.toml("pyproject.toml")
    found = {".": str(toml_table(root, "project").get("requires-python", ""))}
    members = toml_table(root, "tool", "uv", "workspace").get("members", [])
    patterns = [str(m) for m in members] if isinstance(members, list) else []
    for path in sorted(ctx.repo.glob("**/pyproject.toml")):
        folder = path.parent.relative_to(ctx.repo).as_posix()
        if folder != "." and any(fnmatch.fnmatch(folder, p) for p in patterns):
            found[folder] = str(toml_table(ctx.toml(f"{folder}/pyproject.toml"), "project").get("requires-python", ""))
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
            f"raise requires-python to >={pin[0]}.{pin[1]}, or add a CI job running `uv run --python <lower> just test`",
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
        data = ctx.toml(rel)
        floor = (data if rel == "uv.toml" else toml_table(data, "tool", "uv")).get("required-version")
        if floor:
            return passing(f"{rel}: required-version {floor}")
    return not_set_up(
        "no [tool.uv] required-version",
        'add [tool.uv] required-version = ">=<the uv you run>"; setup-uv v5.2.0 and later read it when `version:` is omitted',
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


def _action_version(ref: str, comment: str | None) -> tuple[int, ...]:
    """setup-uv's version from `@v5.2.0`, or from the `# v5.2.0` comment after a commit SHA; () when neither says."""
    for text in (ref, comment or ""):
        if found := re.match(r"^v(\d+(?:\.\d+)*)$", text):
            return tuple(int(n) for n in found.group(1).split("."))
    return ()


def _setup_uv_problems(rel: str, text: str, pin: str, *, exact_floor: bool) -> list[str]:
    problems: list[str] = []
    lines = text.splitlines()
    for at, line in enumerate(lines):
        found = _SETUP_UV.search(line)
        if found is None:
            continue
        indent = len(line) - len(line.lstrip(" -"))
        step: list[str] = []
        for following in lines[at + 1 :]:
            if following.strip() and (len(following) - len(following.lstrip(" -")) < indent or following.lstrip().startswith("- ")):
                break
            step.append(following)
        version = next((m.group(1) for s in step if (m := _STEP_VERSION.match(s))), None)
        action = _action_version(found.group(1), found.group(2))
        if version is not None:
            if version != pin:
                problems.append(f"{rel} setup-uv installs uv {version}, the pin is {pin}")
        elif action < _SETUP_UV_READS_FLOOR:
            shown = ".".join(map(str, action)) or "an unnamed version"
            problems.append(f"{rel} setup-uv {shown} has no `version:` and does not read required-version: it installs the newest uv")
        elif not exact_floor:
            problems.append(f"{rel} setup-uv reads required-version, a range, so it installs the newest uv, not {pin}")
    return problems


def _uv_ci(ctx: Context) -> Finding:
    folder = ctx.repo / _WORKFLOWS
    workflows = sorted(folder.glob("*.y*ml")) if folder.is_dir() else []
    images = dockerfiles(ctx.repo, ctx.profile.ignore)
    installs = [p for p in workflows if "astral-sh/setup-uv" in p.read_text(errors="replace")]
    copies = [p for p in images if _UV_IMAGE.search(p.read_text(errors="replace"))]
    if not installs and not copies:
        return passing("no setup-uv step and no image copies uv; a mise-action CI installs the mise.toml pin")
    pinned = _uv_pin(ctx)
    if pinned is None:
        return not_set_up(
            "CI or an image installs uv, and no exact uv pin to compare it with",
            'pin uv exactly in mise.toml (`uv = "X.Y.Z"`, ADR 0024) and install it in CI with jdx/mise-action',
        )
    pin, where = pinned
    exact_floor = _EXACT_FLOOR.match(str(_floor(ctx) or "").strip()) is not None
    problems = [
        found
        for p in installs
        for found in _setup_uv_problems(p.relative_to(ctx.repo).as_posix(), p.read_text(errors="replace"), pin, exact_floor=exact_floor)
    ]
    for p in copies:
        tags = {m.group(1) or "no tag" for m in _UV_IMAGE.finditer(p.read_text(errors="replace"))}
        problems += [f"{p.relative_to(ctx.repo).as_posix()} copies uv:{tag}, the pin is {pin}" for tag in sorted(tags) if tag != pin]
    if problems:
        return failing(
            "; ".join(problems),
            f'install uv {pin} ({where}) everywhere: in CI with jdx/mise-action (reads mise.toml) or setup-uv `version: "{pin}"`; '
            f"in an image `COPY --from=ghcr.io/astral-sh/uv:{pin}`",
        )
    return passing(f"CI and images install uv {pin}, the {where} pin")


_ROWS = {
    "python-pin": ".python-version pins one X.Y, inside every requires-python range",
    "python-range": 'requires-python is ">=X.Y" everywhere, with no upper cap',
    "python-range-tested": "a lower bound below the pin is run in CI",
    "python-ci": "CI takes Python from .python-version, not a hard-coded version",
    "uv-version": "uv's version floor is declared ([tool.uv] required-version)",
    "uv-ci": "CI and container images install the pinned uv, not the newest",
}


@check_each("stack.python-pin", "python-uv repos pin Python and uv once, honestly, and CI reads the pins", layer="stack")
def python_pin(ctx: Context) -> list[Sub]:
    """Six rows under the python-uv stack."""
    if _STACK not in ctx.profile.stacks:
        return []
    pin, pin_finding = _pin(ctx)
    findings = {
        "python-pin": pin_finding,
        "python-range": _range(ctx),
        "python-range-tested": _range_tested(ctx, pin),
        "python-ci": _ci_python(ctx),
        "uv-version": _uv_version(ctx),
        "uv-ci": _uv_ci(ctx),
    }
    return [Sub(f"stack/{_STACK}", f"stack.{_STACK}.{row}", _ROWS[row], finding) for row, finding in findings.items()]
