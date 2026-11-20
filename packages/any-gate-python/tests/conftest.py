"""A throwaway pytest project to run the stages against."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def project(tmp_path: Path) -> Callable[..., Path]:
    """`project(a="def test_a(): ...", ...)`: `serial` and `quarantine` markers declared, one `test_<name>.py` per keyword."""

    def make(**tests: str) -> Path:
        (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers =\n    serial: runs alone\n    quarantine: flaky, cannot block\n")
        for name, body in tests.items():
            (tmp_path / f"test_{name}.py").write_text(textwrap.dedent(body))
        return tmp_path

    return make
