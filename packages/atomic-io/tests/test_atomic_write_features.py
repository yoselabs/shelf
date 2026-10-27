"""atomic-io's write contract, stated as Gherkin."""

from __future__ import annotations

import json
import stat
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from atomic_io import atomic_write_bytes, atomic_write_json
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    from pathlib import Path

scenarios("features")


@dataclass
class World:
    root: Path
    failure: Exception | None = None


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(root=tmp_path)


@given(parsers.parse('a file "{name}" holding the JSON {payload}'))
def _holding_json(world: World, name: str, payload: str) -> None:
    (world.root / name).write_text(payload, encoding="utf-8")


@given(parsers.parse('a file "{name}" with permissions {octal}'))
def _with_permissions(world: World, name: str, octal: str) -> None:
    path = world.root / name
    path.write_bytes(b"old")
    path.chmod(int(octal, 8))


@when(parsers.parse('the JSON {payload} is written atomically to "{name}"'))
def _write_json(world: World, payload: str, name: str) -> None:
    atomic_write_json(world.root / name, json.loads(payload))


@when(parsers.parse('a value JSON cannot encode is written atomically to "{name}"'))
def _write_unencodable(world: World, name: str) -> None:
    try:
        atomic_write_json(world.root / name, {"bad": object()})
    except TypeError as exc:
        world.failure = exc


@when(parsers.parse('the bytes "{text}" are written atomically to "{name}" keeping its mode'))
def _write_keep_mode(world: World, text: str, name: str) -> None:
    atomic_write_bytes(world.root / name, text.encode(), keep_mode=True)


@when(parsers.parse('the bytes "{text}" are written atomically to "{name}" without fsync'))
def _write_no_fsync(world: World, text: str, name: str) -> None:
    atomic_write_bytes(world.root / name, text.encode(), fsync=False)


@when(parsers.parse('the bytes "{text}" are written atomically to "{name}"'))
def _write_plain(world: World, text: str, name: str) -> None:
    atomic_write_bytes(world.root / name, text.encode())


@then(parsers.parse('"{name}" holds the JSON {payload}'))
def _holds_json(world: World, name: str, payload: str) -> None:
    assert json.loads((world.root / name).read_text(encoding="utf-8")) == json.loads(payload)


@then(parsers.parse('"{name}" holds the bytes "{text}"'))
def _holds_bytes(world: World, name: str, text: str) -> None:
    assert (world.root / name).read_bytes() == text.encode()


@then(parsers.parse('"{name}" has permissions {octal}'))
def _has_permissions(world: World, name: str, octal: str) -> None:
    assert stat.S_IMODE((world.root / name).stat().st_mode) == int(octal, 8)


@then("no temp file is left beside it")
def _no_temp(world: World) -> None:
    assert list(world.root.glob(".*.tmp")) == []


@then("the write is refused")
def _refused(world: World) -> None:
    assert isinstance(world.failure, TypeError)
