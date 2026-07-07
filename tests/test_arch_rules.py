"""Architectural fitness rules — blocking, intra-package (resolution 0005).

Native reimplementation of a2kit's Rego policies (no OPA). These BLOCK on within-package
findings; cross-package duplication is advisory only (`make advisory`), because
constitution VI values some duplication ("cheaper than the wrong abstraction").
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

import arch_rules  # noqa: E402  -- path-injected tool module, imported after sys.path setup


def _allowlist(section: str) -> dict[str, str]:
    entry = arch_rules.load_allowlist().get(section, {})
    return entry if isinstance(entry, dict) else {}


def _body_dup_pairs() -> set[frozenset[str]]:
    raw = arch_rules.load_allowlist().get("body_dup", [])
    rows = raw if isinstance(raw, list) else []
    return {frozenset(str(n) for n in row["names"]) for row in rows}


def test_no_runtime_dep_without_upper_bound() -> None:
    # RG004 — an unbounded dep breaks silently on a major bump (see resolution 0001's ethos).
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
