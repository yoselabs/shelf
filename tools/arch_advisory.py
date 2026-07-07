#!/usr/bin/env python3
"""Cross-package architectural advisories — NON-blocking (resolution 0005).

Within a package, duplication is a bug (blocked by ``tests/test_arch_rules.py``).
*Across* packages it is a signal, not a sin: constitution VI values some duplication,
and a body shared by two packages is a candidate for a T0 primitive (rule of three).
So this reports, never fails. Run it with ``make advisory``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import arch_rules


def main() -> int:
    facts = arch_rules.function_facts()
    dups = arch_rules.body_dups(facts, cross_package=True)
    collisions = arch_rules.name_collisions(facts, cross_package=True)

    if not dups and not collisions:
        print("advisory: no cross-package duplication or name collisions — nothing to consider.")
        return 0

    print("advisory (non-blocking) — cross-package signals worth a look:\n")
    for a, b in dups:
        print(f"  body shared across packages: {a.package}:{a.name} ({a.file}:{a.line})")
        print(f"                            ~= {b.package}:{b.name} ({b.file}:{b.line})")
        print("    -> consider promoting a canonical impl to a T0 primitive (rule of three).")
    for a, b in collisions:
        print(f"  private name {a.name!r} in two packages: {a.file}:{a.line}  &  {b.file}:{b.line}")
        print("    -> may be independent, or a shared helper waiting to be lifted.")
    print("\n(Advisory only. Do NOT force the abstraction — constitution VI.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
