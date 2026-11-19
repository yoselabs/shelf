"""The ruff preset rejects each raw tool the primitive replaces."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from any_pipeline.preset import BANNED, ruff_config

if TYPE_CHECKING:
    from pathlib import Path

_USES = {
    "threading": "import threading\nthreading.Thread(target=print)\n",
    "concurrent.futures": "import concurrent.futures\nconcurrent.futures.ThreadPoolExecutor()\n",
    "asyncio.gather": "import asyncio\n\n\nasync def f() -> None:\n    await asyncio.gather()\n",
    "asyncio.create_task": "import asyncio\n\n\nasync def f() -> None:\n    asyncio.create_task(f())\n",
    "time.sleep": "import time\ntime.sleep(1)\n",
}


def _ruff(tmp_path: Path, code: str) -> str:
    (tmp_path / "ruff.toml").write_text(ruff_config(), encoding="utf-8")
    source = tmp_path / "mod.py"
    source.write_text(code, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--config", str(tmp_path / "ruff.toml"), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout


def test_every_banned_name_has_a_use_that_is_rejected() -> None:
    assert set(_USES) == set(BANNED)


@pytest.mark.parametrize("name", sorted(_USES))
def test_the_preset_rejects(name: str, tmp_path: Path) -> None:
    assert "TID251" in _ruff(tmp_path, _USES[name])


def test_a_bare_except_and_a_blocking_call_in_async_code_are_rejected(tmp_path: Path) -> None:
    out = _ruff(
        tmp_path,
        "import subprocess\n\n\nasync def f() -> None:\n    subprocess.run(['x'], check=False)\n"
        "    try:\n        pass\n    except:\n        pass\n",
    )
    assert "E722" in out and "ASYNC" in out


def test_the_stage_vocabulary_itself_is_allowed(tmp_path: Path) -> None:
    assert "TID251" not in _ruff(tmp_path, "from any_pipeline import gather\n")
