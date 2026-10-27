"""app-dirs' folder rules, stated as Gherkin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from app_dirs import cache_dir, config_dir, state_dir
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    from collections.abc import Callable

scenarios("features")

_KINDS: dict[str, Callable[..., Path]] = {"config": config_dir, "state": state_dir, "cache": cache_dir}


@dataclass
class World:
    home: Path = Path("/home/me")
    env: dict[str, str] = field(default_factory=dict)
    folder: Path | None = None
    refused: bool = False


@pytest.fixture
def world() -> World:
    return World()


@given(parsers.parse('the environment sets {variable} to "{value}"'))
def _set(world: World, variable: str, value: str) -> None:
    world.env[variable] = value


@given("a real home folder")
def _real_home(world: World, tmp_path: Path) -> None:
    world.home = tmp_path


@when(parsers.parse('the {kind} folder of "{app}" is asked for with the plugin data folder'))
def _ask_plugin(world: World, kind: str, app: str) -> None:
    world.folder = _KINDS[kind](app, env=world.env, home=world.home, plugin_data=True)


@when(parsers.parse('the {kind} folder of "{app}" is asked for and created'))
def _ask_create(world: World, kind: str, app: str) -> None:
    world.folder = _KINDS[kind](app, env=world.env, home=world.home, create=True)


@when(parsers.parse('the {kind} folder of "{app}" is asked for'))
def _ask(world: World, kind: str, app: str) -> None:
    try:
        world.folder = _KINDS[kind](app, env=world.env, home=world.home)
    except ValueError:
        world.refused = True


@then(parsers.parse('the folder is "{folder}"'))
def _is(world: World, folder: str) -> None:
    assert world.folder == Path(folder)


@then("the folder does not exist")
def _absent(world: World) -> None:
    assert world.folder is not None
    assert not world.folder.exists()


@then("the folder exists")
def _present(world: World) -> None:
    assert world.folder is not None
    assert world.folder.is_dir()


@then("the name is refused")
def _name_refused(world: World) -> None:
    assert world.refused
