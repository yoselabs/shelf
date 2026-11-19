from __future__ import annotations

import pytest

from any_pipeline import Limit, Stage, gather

L = Limit(calls=2, seconds=5.0, tries=1)


async def to_int(x: str) -> int:
    return len(x)


async def to_float(x: str) -> float:
    return float(len(x))


async def inc(x: int) -> int:
    return x + 1


async def add(p: tuple[int, float]) -> float:
    return p[0] + p[1]


@pytest.mark.parametrize("bad", [{"calls": 0}, {"calls": -1}, {"seconds": 0.0}, {"tries": 0}])
def test_a_limit_with_a_zero_or_negative_number_is_refused(bad: dict[str, float]) -> None:
    with pytest.raises(ValueError, match=r"positive|at least"):
        Limit(**{"calls": 1, "seconds": 1.0, "tries": 1, **bad})  # type: ignore[arg-type]  # the table of bad numbers


def test_two_stages_with_one_name_cannot_be_composed() -> None:
    with pytest.raises(ValueError, match="twice"):
        Stage("a", to_int, L) >> Stage("a", inc, L)
    same = Stage("x", to_int, L)
    with pytest.raises(ValueError, match="twice"):
        gather(same, same)


def test_composition_is_a_value_and_names_its_stages() -> None:
    pipeline = gather(Stage("i", to_int, L), Stage("f", to_float, L)) >> Stage("add", add, L)
    assert [s.name for s in pipeline.leaves()] == ["i", "f", "add"]
