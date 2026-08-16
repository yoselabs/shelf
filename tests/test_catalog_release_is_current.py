"""The catalog's `release` field must name the version the package actually is.

The catalog README is the surface a consuming agent reads to decide what to
adopt and which tag to pin. `release` is hand-maintained, and until 2026-08-02
nothing compared it to anything — so it drifted, silently, in one direction:

    convert-md        catalog said v0.3.0   package was v0.8.0   (5 releases behind)
    content-extract   catalog said v0.1.1   package was v0.2.0
    http-fetch        catalog said v0.1.0   package was v0.2.0
    record-mine       catalog said v0.1.0   package was v0.2.0
    llm-cache         catalog said v0.1.1   package was v0.1.2
    mcp-result-wire   catalog said nothing  package was v0.1.0, tagged

Six of twenty-six. The failure mode is quiet and asymmetric: an understated
`release` never breaks a build, it just means a consumer pins an older tag, or
reads the catalog and concludes a capability it needs is not there yet. Nobody
gets an error; they get an out-of-date shelf.

**This is the third instance of one shape** — a hand-maintained list with
nothing checking it against the thing it describes. The first was a2web's
`tach.toml` module list (a new package silently gets no boundary contract); the
second was this repo's own `testpaths` (8 of 26 package suites ran nowhere). At
three, the general answer is the rule rather than the individual fixes: **a
hand-maintained restatement of a fact the repo already knows must be checked
against that fact by a test, or it must not be hand-maintained.**

Asserted against `pyproject.toml`, deliberately, NOT against `git tag`. The
promote loop bumps the version and runs `make check` BEFORE tagging (steps 4
then 5), so a tag-based check would fail every release at exactly the moment it
is supposed to pass, and would be disabled within a week. The version file is
the fact; the tag follows it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CATALOG = _ROOT / "catalog"
_PACKAGES = _ROOT / "packages"
_SKILLS = _ROOT / "skills"

#: `kind = "skill"` entries live under skills/<name>/, not packages/<name>/ — a
#: different Kind, a different unit dir (skill-as-shelf-kind). Their release currency
#: is asserted separately once a real skill exists (skill-kind capability, requirement
#: "A skill member's always-on token cost is asserted"); this file stays package-only.
_SKILL_KIND = "skill"

#: Population floor — the catalog is ~26 entries. Without this, a moved or
#: renamed catalog directory finds zero files to object to and reports green,
#: which is the exact failure this whole file exists to make impossible.
_MIN_ENTRIES = 20


def _entries() -> list[tuple[str, dict[str, object], Path]]:
    """Every catalog entry as `(name, parsed toml, path)`."""
    out = []
    for path in sorted(_CATALOG.glob("*.toml")):
        cfg = tomllib.loads(path.read_text(encoding="utf-8"))
        out.append((str(cfg["name"]), cfg, path))
    return out


def test_the_walk_found_the_catalog() -> None:
    """Anti-vacuity: the checks below are worthless over an empty glob."""
    entries = _entries()
    assert len(entries) >= _MIN_ENTRIES, f"only {len(entries)} catalog entries found under {_CATALOG} — expected at least {_MIN_ENTRIES}"


def test_every_catalog_entry_names_a_real_package_or_skill() -> None:
    """A catalog entry for a unit that does not exist on disk is a dangling promise."""
    missing = [
        name
        for name, cfg, _ in _entries()
        if not (
            (_SKILLS / name / "SKILL.md").is_file() if cfg.get("kind") == _SKILL_KIND else (_PACKAGES / name / "pyproject.toml").is_file()
        )
    ]
    assert not missing, f"catalog entries with no package/skill on disk: {missing}"


def test_every_package_has_a_catalog_entry() -> None:
    """The reverse direction — an uncatalogued package is invisible to consumers."""
    catalogued = {name for name, _, _ in _entries()}
    on_disk = {p.parent.name for p in _PACKAGES.glob("*/pyproject.toml")}
    assert on_disk, "no packages found — the walk is vacuous"
    uncatalogued = sorted(on_disk - catalogued)
    assert not uncatalogued, f"package(s) with no catalog entry, so no consumer can find them: {uncatalogued}"


def test_catalog_release_matches_the_package_version() -> None:
    """`release` must be `<name>-v<version from that package's pyproject>`.

    Both a missing field and a stale one fail: `mcp-result-wire` had no
    `release` at all while being tagged, and absence reads to a consumer exactly
    like "not released yet".
    """
    drifted: list[str] = []
    for name, cfg, path in _entries():
        if cfg.get("kind") == _SKILL_KIND:
            continue  # skill release currency is asserted separately (skill-kind capability)
        version = tomllib.loads((_PACKAGES / name / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        expected = f"{name}-v{version}"
        actual = cfg.get("release")
        if actual != expected:
            shown = "<absent>" if actual is None else str(actual)
            drifted.append(f"{path.name}: release={shown}, package version is {version} (expected {expected!r})")

    assert not drifted, (
        "catalog `release` disagrees with the package's own version:\n  "
        + "\n  ".join(drifted)
        + "\n\nBump `release` in the same change as the version. A stale `release` never breaks "
        "a build — it just makes a consumer pin an older tag or conclude a capability is missing."
    )
