"""Fixtures over the scripted bd."""

from __future__ import annotations

import pytest

from beads_client import Bd
from beads_client.testing import Script


@pytest.fixture
def script() -> Script:
    return Script()


@pytest.fixture
def bd(script: Script) -> Bd:
    return Bd("tester", exe="bd", run=script, sleep=lambda _s: None)
