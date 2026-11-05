"""One-slot mailbox: merge under lock, take once, peek without the lock."""

from __future__ import annotations

import contextlib
import multiprocessing
from typing import TYPE_CHECKING

from any_mailbox import Mailbox

if TYPE_CHECKING:
    from pathlib import Path


def _append(path: str, token: bytes) -> None:
    Mailbox(__import__("pathlib").Path(path)).post(lambda old: (old or b"") + token)


def test_empty_mailbox_peeks_and_takes_none(tmp_path: Path) -> None:
    box = Mailbox(tmp_path / "box")
    assert box.peek() is None
    assert box.take() is None


def test_post_sees_none_then_the_waiting_message(tmp_path: Path) -> None:
    box = Mailbox(tmp_path / "box")
    seen: list[bytes | None] = []

    def update(old: bytes | None) -> bytes:
        seen.append(old)
        return (old or b"") + b"x"

    assert box.post(update) is True
    assert box.post(update) is True
    assert seen == [None, b"x"]
    assert box.peek() == b"xx"


def test_take_hands_over_once_and_removes(tmp_path: Path) -> None:
    box = Mailbox(tmp_path / "box")
    box.post(lambda _old: b"hello")
    assert box.take() == b"hello"
    assert box.take() is None
    assert box.peek() is None


def test_peek_leaves_the_message(tmp_path: Path) -> None:
    box = Mailbox(tmp_path / "box")
    box.post(lambda _old: b"m")
    assert box.peek() == b"m"
    assert box.peek() == b"m"


def test_post_returning_none_refuses_without_writing(tmp_path: Path) -> None:
    box = Mailbox(tmp_path / "box")
    assert box.post(lambda _old: None) is False
    assert box.peek() is None
    box.post(lambda _old: b"keep")
    assert box.post(lambda _old: None) is False
    assert box.peek() == b"keep"


def test_post_raising_leaves_the_message_and_frees_the_lock(tmp_path: Path) -> None:
    box = Mailbox(tmp_path / "box", timeout=0)
    box.post(lambda _old: b"keep")

    def boom(_old: bytes | None) -> bytes:
        raise RuntimeError

    with contextlib.suppress(RuntimeError):
        box.post(boom)
    assert box.peek() == b"keep"
    assert box.post(lambda old: (old or b"") + b"!") is True


def test_default_lock_sits_beside_the_path_and_parents_are_made(tmp_path: Path) -> None:
    box = Mailbox(tmp_path / "deep" / "box")
    box.post(lambda _old: b"m")
    assert (tmp_path / "deep" / "box.lock").exists()
    assert Mailbox(tmp_path / "a" / "box", tmp_path / "other" / "l").lock == tmp_path / "other" / "l"


def test_concurrent_posts_from_processes_lose_nothing(tmp_path: Path) -> None:
    path = tmp_path / "box"
    ctx = multiprocessing.get_context("spawn")
    procs = [ctx.Process(target=_append, args=(str(path), bytes([65 + i]))) for i in range(6)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
        assert p.exitcode == 0
    assert sorted(Mailbox(path).peek() or b"") == sorted(bytes([65 + i])[0] for i in range(6))
