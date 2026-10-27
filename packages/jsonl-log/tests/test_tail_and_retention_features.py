"""jsonl-log's multi-process append, byte-cursor reader and age retention, stated as Gherkin."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from jsonl_log import Jsonl, JsonlLog
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    from pathlib import Path

scenarios("features")

_DAY = 86400.0
_WRITER = """
import sys
from jsonl_log import JsonlLog
tag = sys.argv[2]
with JsonlLog.open(sys.argv[1]) as log:
    for i in range(50):
        log.append_json({"tag": tag, "i": i, "pad": "x" * 20000})
"""


@dataclass
class World:
    path: Path
    log: Jsonl = field(init=False)
    cursor: int = 0
    got: list[dict[str, Any]] = field(default_factory=list)
    offset: int = 0
    size_before: int = 0

    def __post_init__(self) -> None:
        self.log = Jsonl(self.path)


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path / "log.jsonl")


def _numbers(world: World) -> list[int]:
    return [row["n"] for row in world.got]


@given(parsers.parse("a log holding the lines {first} and {second}"))
def _holding(world: World, first: str, second: str) -> None:
    for text in (first, second):
        world.log.append(json.loads(text))


@given(parsers.parse('a log holding the raw lines "{a}", "{b}" and {c}'))
def _raw(world: World, a: str, b: str, c: str) -> None:
    world.path.write_text(f"{a}\n{b}\n{c}\n", encoding="utf-8")


@given("an empty log")
def _empty(world: World) -> None:
    world.path.write_bytes(b"")


@given("a rotating log with two rotated files, one written 8 days ago and one 1 day ago")
def _rotated(world: World) -> None:
    for n, age in ((1, 1), (2, 8)):
        rotated = world.path.with_name(f"log.jsonl.{n}")
        rotated.write_text('{"n": 1}\n', encoding="utf-8")
        then_ = time.time() - age * _DAY
        os.utime(rotated, (then_, then_))


@when("a reader reads from the start")
def _from_start(world: World) -> None:
    world.got, world.cursor = _read(world, 0)


@when("the reader reads from its cursor")
def _from_cursor(world: World) -> None:
    world.got, world.cursor = _read(world, world.cursor)


def _read(world: World, offset: int) -> tuple[list[dict[str, Any]], int]:
    entries, cursor = world.log.read_from(offset)
    return [e.data for e in entries], cursor


@when(parsers.parse("a writer has written {line} only up to its half"))
def _half(world: World, line: str) -> None:
    text = json.dumps(json.loads(line))
    with world.path.open("ab") as handle:
        _ = handle.write(text[: len(text) // 2].encode())


@when("the writer finishes the line")
def _finish(world: World) -> None:
    text = json.dumps({"n": 3})
    with world.path.open("ab") as handle:
        _ = handle.write((text[len(text) // 2 :] + "\n").encode())


@when(parsers.parse("{line} is appended"))
def _append(world: World, line: str) -> None:
    world.size_before = world.log.size()
    world.offset = world.log.append(json.loads(line))


@when(parsers.parse("{count:d} processes each append 50 long lines"))
def _processes(world: World, count: int) -> None:
    procs = [subprocess.Popen([sys.executable, "-c", _WRITER, str(world.path), str(i)]) for i in range(count)]
    assert [p.wait(timeout=120) for p in procs] == [0] * count


@when("the log is pruned with a limit of 7 days")
def _prune(world: World) -> None:
    with JsonlLog.open(world.path, max_age=7 * _DAY) as log:
        _ = log.prune()


@then(parsers.re(r"it gets the lines (?P<numbers>\d+(?: and \d+)?)"))
def _gets(world: World, numbers: str) -> None:
    assert _numbers(world) == [int(n) for n in numbers.split(" and ")]


@then("it gets no lines")
def _gets_none(world: World) -> None:
    assert world.got == []


@then("the reported offset is the size the log had before")
def _offset(world: World) -> None:
    assert world.offset == world.size_before


@then(parsers.parse("the last 2 lines are {a:d} and {b:d}"))
def _last(world: World, a: int, b: int) -> None:
    assert [e.data["n"] for e in world.log.tail(2)] == [a, b]


@then(parsers.parse("the log holds {count:d} whole lines"))
def _whole(world: World, count: int) -> None:
    lines = world.path.read_bytes().split(b"\n")
    assert lines.pop() == b""
    rows = [json.loads(line) for line in lines]
    assert len(rows) == count
    assert sorted((r["tag"], r["i"]) for r in rows) == sorted((str(t), i) for t in range(4) for i in range(50))


@then("only the file written 1 day ago is left")
def _left(world: World) -> None:
    assert world.path.with_name("log.jsonl.1").exists()
    assert not world.path.with_name("log.jsonl.2").exists()
