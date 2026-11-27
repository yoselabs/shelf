"""The `reads` map in `[tool.any-gate.python]` (root file -> packages whose tests read it) must hold what the tests say.

A mapped root file selects only its readers; a test naming a mapped file that its package is not mapped for would pass unrun the day the
file changes. The scan is static (see `any_gate_python.reads_audit` for what it cannot see).
"""

from __future__ import annotations

from pathlib import Path

from any_gate_python import reads_audit

ROOT = Path(__file__).resolve().parents[1]


def test_no_test_names_a_mapped_root_file_its_package_is_not_mapped_for() -> None:
    assert reads_audit.audit(ROOT) == []


def test_every_repo_test_is_keyed_for_what_it_names() -> None:
    assert reads_audit.audit_repo_tests(ROOT) == []
