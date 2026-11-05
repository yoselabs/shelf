"""Architectural fitness rules — blocking, intra-package (ADR 0005).

Native reimplementation of a2kit's Rego policies (no OPA). These BLOCK on within-package
findings; cross-package body duplication blocks too (Article III, no redundancy). Cross-package
private-name collisions are not checked: the same name over different bodies is not redundancy.
"""

import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

import arch_rules  # noqa: E402  -- path-injected tool module, imported after sys.path setup

_PACKAGES = _ROOT / "packages"


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name.strip().lower())


def _src_import_names() -> set[str]:
    return {p.name for p in _PACKAGES.glob("*/src/*") if p.is_dir() and p.name.isidentifier()}


def _importlinter_config() -> dict[str, Any]:
    config: dict[str, Any] = tomllib.loads((_ROOT / "pyproject.toml").read_text())["tool"]["importlinter"]
    return config


def _declared_workspace_edges() -> set[tuple[str, str]]:
    """(importing, imported) import-name pairs: each package's own dependencies and extras that name another workspace member."""
    projects = {pyproject: tomllib.loads(pyproject.read_text())["project"] for pyproject in _PACKAGES.glob("*/pyproject.toml")}
    import_name = {
        _normalize(project["name"]): next(p.name for p in (pyproject.parent / "src").iterdir() if p.is_dir() and p.name.isidentifier())
        for pyproject, project in projects.items()
    }
    edges: set[tuple[str, str]] = set()
    for project in projects.values():
        specs = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            specs += extra
        for spec in specs:
            dep = _normalize(re.split(r"[\s<>=!~;\[]", spec.strip(), maxsplit=1)[0])
            if dep in import_name:
                edges.add((import_name[_normalize(project["name"])], import_name[dep]))
    return edges


def test_every_package_is_an_import_linter_root() -> None:
    # A package added to packages/ and not to root_packages would sit outside both contracts.
    config = _importlinter_config()
    roots = set(config["root_packages"])
    on_disk = _src_import_names()
    assert roots == on_disk, f"[tool.importlinter] root_packages differs from packages/*/src: {sorted(roots ^ on_disk)}"
    for contract in config["contracts"]:
        listed = set(contract.get("source_modules") or contract.get("modules") or [])
        assert listed == roots, f"contract {contract['name']!r} lists a different package set: {sorted(listed ^ roots)}"


def test_independence_ignore_list_is_the_declared_workspace_dependencies() -> None:
    # The only allowed sibling edges are the ones a package declares in its own pyproject; two lists, kept equal here.
    independence = next(c for c in _importlinter_config()["contracts"] if c["type"] == "independence")
    pairs = (edge.split("->") for edge in independence["ignore_imports"])
    allowed = {(importer.strip().split(".")[0], imported.strip().split(".")[0]) for importer, imported in pairs}
    declared = _declared_workspace_edges()
    assert allowed == declared, (
        f"ignore_imports vs declared deps: only ignored {sorted(allowed - declared)}, only declared {sorted(declared - allowed)}"
    )


def _allowlist(section: str) -> dict[str, str]:
    entry = arch_rules.load_allowlist().get(section, {})
    return entry if isinstance(entry, dict) else {}


def _body_dup_pairs() -> set[frozenset[str]]:
    raw = arch_rules.load_allowlist().get("body_dup", [])
    rows = raw if isinstance(raw, list) else []
    return {frozenset(str(n) for n in row["names"]) for row in rows}


def test_no_runtime_dep_without_upper_bound() -> None:
    # RG004 — an unbounded dep breaks silently on a major bump (see ADR 0001's ethos).
    allow = _allowlist("dep_upper_bound")
    offenders = [(pkg, spec) for pkg, spec in arch_rules.unbounded_deps() if arch_rules.dep_name(spec) not in allow]
    assert not offenders, f"runtime deps without an upper bound (add `<X` or allowlist w/ reason): {offenders}"


def test_no_intra_package_body_duplication() -> None:
    # RG001 — copy-pasted / renamed-but-identical bodies WITHIN one package should be one function.
    facts = arch_rules.function_facts()
    allowed = _body_dup_pairs()
    dups = [
        (a.file, a.name, b.file, b.name)
        for a, b in arch_rules.body_dups(facts, cross_package=False)
        if frozenset({a.name, b.name}) not in allowed
    ]
    assert not dups, f"duplicated function bodies within a package (extract a canonical impl): {dups}"


def test_no_cross_package_body_duplication() -> None:
    # Article III — one implementation of a behaviour per repo. No allowlist: lift it to one package or file a task.
    dups = [(a.file, a.name, b.file, b.name) for a, b in arch_rules.body_dups(arch_rules.function_facts(), cross_package=True)]
    assert not dups, (
        f"function bodies duplicated across packages (lift the shared body to one package; filing a task does not pass the gate): {dups}"
    )


_TOTAL = """
def {name}(items):
    total = 0
    for item in items:
        total += item
    return total
"""
_PRODUCT = """
def {name}(items):
    total = 1
    for item in items:
        total *= item
    return total
"""


def _two_packages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first: str, second: str) -> list[arch_rules.FunctionFact]:
    for package, source in (("pa", first), ("pb", second)):
        module = tmp_path / "packages" / package / "src" / package / "mod.py"
        module.parent.mkdir(parents=True)
        module.write_text(source)
    monkeypatch.setattr(arch_rules, "_ROOT", tmp_path)
    monkeypatch.setattr(arch_rules, "_PACKAGES", tmp_path / "packages")
    return arch_rules.function_facts()


def test_cross_package_check_reports_a_renamed_identical_body(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    facts = _two_packages(tmp_path, monkeypatch, _TOTAL.format(name="add_up"), _TOTAL.format(name="sum_all"))
    assert [(a.name, b.name) for a, b in arch_rules.body_dups(facts, cross_package=True)] == [("add_up", "sum_all")]


def test_cross_package_check_passes_bodies_of_a_different_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    facts = _two_packages(tmp_path, monkeypatch, _TOTAL.format(name="fold"), _PRODUCT.format(name="fold"))
    assert arch_rules.body_dups(facts, cross_package=True) == []


def test_no_intra_package_private_name_collision() -> None:
    # RG002 — the same private helper name in two files usually means a re-implementation.
    facts = arch_rules.function_facts()
    allow = _allowlist("name_collision")
    collisions = [(a.file, b.file, a.name) for a, b in arch_rules.name_collisions(facts, cross_package=False) if a.name not in allow]
    assert not collisions, f"private helper names reused across files (lift to a shared module): {collisions}"


def test_allowlist_entries_carry_a_reason() -> None:
    # RG003 — a suppression without a rationale is how rules rot.
    allowlist = arch_rules.load_allowlist()
    for section in ("dep_upper_bound", "name_collision"):
        for name, reason in _allowlist(section).items():
            assert str(reason).strip(), f"{section} allowlist entry {name!r} has no reason"
    raw = allowlist.get("body_dup", [])
    for row in raw if isinstance(raw, list) else []:
        assert str(row.get("reason", "")).strip(), f"body_dup allowlist entry {row.get('names')} has no reason"
