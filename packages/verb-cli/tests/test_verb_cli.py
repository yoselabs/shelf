"""A signature becomes flags (moved from a2kay tests/test_cli_verbs.py, the flag machinery)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, Field
from verb_cli import FlagJsonError, VerbCliError, flags_of, kwargs_of, to_argparse


class _Where(BaseModel):
    field: str
    value: int


class _Router:
    async def read(
        self,
        type_: Annotated[str, Field(alias="type", description="the kind")],
        id_: Annotated[str, Field(alias="id")],
        *args: str,
        where: _Where | None = None,
        **kwargs: str,
    ) -> None: ...


def _parse(fn: object, argv: list[str]) -> dict[str, object]:
    parser = argparse.ArgumentParser(exit_on_error=False)
    specs = flags_of(fn)  # type: ignore[arg-type]
    to_argparse(parser, specs)
    return kwargs_of(parser.parse_args(argv), specs)


def test_the_alias_names_the_flag_and_the_description_is_the_help() -> None:
    specs = flags_of(_Router().read)
    assert [(s.dest, s.flag, s.required, s.help) for s in specs] == [
        ("type_", "--type", True, "the kind"),
        ("id_", "--id", True, None),
        ("where", "--where", False, None),
    ]


def test_a_model_flag_is_json_validated_into_the_model() -> None:
    kwargs = _parse(_Router().read, ["--type", "project", "--id", "p1", "--where", '{"field": "n", "value": 3}'])
    assert kwargs == {"type_": "project", "id_": "p1", "where": _Where(field="n", value=3)}


def test_bool_param_becomes_a_paired_flag() -> None:
    async def sample(*, dry_run: bool = False) -> None: ...

    assert _parse(sample, ["--dry-run"]) == {"dry_run": True}
    assert _parse(sample, ["--no-dry-run"]) == {"dry_run": False}
    assert _parse(sample, []) == {"dry_run": False}  # signature default


def test_container_param_is_one_json_flag() -> None:
    async def sample(*, frontmatter: dict | None = None, tags: list[str] | None = None) -> None: ...

    assert _parse(sample, ["--frontmatter", '{"a":1}', "--tags", '["x"]']) == {"frontmatter": {"a": 1}, "tags": ["x"]}


def test_int_path_and_optional_flags() -> None:
    async def sample(*, limit: int = 8, ratio: float = 0.5, root: Path | None = None, cursor: str | None = None) -> None: ...

    kwargs = _parse(sample, ["--limit", "20", "--ratio", "0.25", "--root", "a/b"])
    assert kwargs == {"limit": 20, "ratio": 0.25, "root": Path("a/b"), "cursor": None}


def test_a_json_flag_left_out_keeps_its_default() -> None:
    async def sample(*, bound: Literal["wire", "store"] = "wire") -> None: ...

    assert _parse(sample, []) == {}
    assert _parse(sample, ["--bound", '"store"']) == {"bound": "store"}


def test_a_missing_required_flag_is_a_usage_error() -> None:
    async def sample(name: str) -> None: ...

    with pytest.raises(argparse.ArgumentError):
        _parse(sample, [])


def test_invalid_json_names_the_flag() -> None:
    async def sample(*, frontmatter_extra: Annotated[dict | None, Field(alias="fm")] = None) -> None: ...

    with pytest.raises(FlagJsonError) as caught:
        _parse(sample, ["--fm", "{nope"])
    assert caught.value.flag == "--fm"
    assert caught.value.value == "{nope"
    assert str(caught.value).startswith("--fm: invalid JSON (")
    assert isinstance(caught.value, VerbCliError)


def test_an_unannotated_parameter_is_text() -> None:
    def sample(name, count=1):  # type: ignore[no-untyped-def]
        ...

    assert _parse(sample, ["--name", "x"]) == {"name": "x", "count": 1}
