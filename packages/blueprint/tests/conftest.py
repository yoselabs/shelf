"""A throwaway git repo per test (blueprint.testing.Repo)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from blueprint.testing import Repo

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo.create(tmp_path / "repo", tmp_path / "bin")
