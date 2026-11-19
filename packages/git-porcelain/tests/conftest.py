"""A scenario tagged ``@real_only`` names a gap of FakeRepo (the feature says which); it runs on the real git only."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import pytest
import stream_proc
from stream_proc import CapturedBytes

if TYPE_CHECKING:
    from collections.abc import Callable


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    gone = [
        item
        for item in items
        if item.get_closest_marker("real_only") is not None
        and getattr(getattr(item, "callspec", None), "params", {}).get("implementation") == "fake"
    ]
    if gone:
        config.hook.pytest_deselected(items=gone)
        items[:] = [item for item in items if item not in gone]


@pytest.fixture
def git_process(monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable[..., subprocess.CompletedProcess[Any]]], None]:
    """Install a fake git child for both runners: the repo runner (``stream_proc.capture_bytes``) and the path API
    (``subprocess.run``). The fake gets ``(argv, env=, timeout=, input=)`` and returns a ``CompletedProcess`` (text or
    bytes) or raises ``subprocess.TimeoutExpired``."""

    def install(process: Callable[..., subprocess.CompletedProcess[Any]]) -> None:
        def capture_bytes(argv: Any, *, env: Any = None, timeout: float, input: Any = None, **_: object) -> CapturedBytes:  # noqa: A002
            try:
                done = process(list(argv), env=env, timeout=timeout, input=input)
            except subprocess.TimeoutExpired as exc:
                return CapturedBytes(124, exc.stdout or b"", exc.stderr or b"", 0.0, True)
            out, err = (x.encode() if isinstance(x, str) else x for x in (done.stdout, done.stderr))
            return CapturedBytes(done.returncode, out, err, 0.0, False)

        monkeypatch.setattr(subprocess, "run", process)
        monkeypatch.setattr(stream_proc, "capture_bytes", capture_bytes)

    return install
