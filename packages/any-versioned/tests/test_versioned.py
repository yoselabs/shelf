from __future__ import annotations

from typing import Any

import pytest

from any_versioned import UnknownVersionError, Versioned


def _v1_to_v2(body: dict[str, Any]) -> dict[str, Any]:  # Any: a stored JSON document
    return {**{k: v for k, v in body.items() if k != "label"}, "name": body["label"]}


V2 = Versioned(current=2, migrations={1: _v1_to_v2})


def test_stamp_puts_the_version_key_first_then_the_body() -> None:
    stamped = V2.stamp({"name": "a", "n": 1})
    assert list(stamped) == ["version", "name", "n"]
    assert stamped["version"] == 2


def test_a_current_document_reads_back_its_body_without_the_version_key() -> None:
    assert V2.read(V2.stamp({"name": "a"})) == {"name": "a"}


def test_an_old_document_is_migrated_to_the_current_body() -> None:
    assert V2.read({"version": 1, "label": "a", "n": 1}) == {"name": "a", "n": 1}


def test_migrations_run_in_order_across_several_steps() -> None:
    chain = Versioned(current=4, migrations={1: lambda b: {**b, "a": 1}, 2: lambda b: {**b, "b": b["a"] + 1}, 3: lambda b: {**b, "c": 3}})
    assert chain.read({"version": 1}) == {"a": 1, "b": 2, "c": 3}
    assert chain.read({"version": 3}) == {"c": 3}


def test_reading_does_not_change_the_loaded_document() -> None:
    raw = {"version": 1, "label": "a"}
    V2.read(raw)
    assert raw == {"version": 1, "label": "a"}


@pytest.mark.parametrize("found", [0, 3, 99, -1, "2", None, 2.5, True])
def test_an_unknown_version_raises_and_names_the_readable_ones(found: object) -> None:
    with pytest.raises(UnknownVersionError, match=r"readable: 1, 2"):
        V2.read({"version": found})


def test_a_missing_version_key_is_unknown() -> None:
    with pytest.raises(UnknownVersionError, match="no 'version'"):
        V2.read({"name": "a"})


def test_a_document_that_is_not_an_object_is_unknown() -> None:
    with pytest.raises(UnknownVersionError):
        V2.read([1, 2])  # type: ignore[arg-type]  # what json.loads may hand over


def test_too_new_says_so() -> None:
    with pytest.raises(UnknownVersionError, match="newer"):
        V2.read({"version": 3})


def test_the_error_is_a_value_error() -> None:
    assert issubclass(UnknownVersionError, ValueError)


def test_the_version_key_has_a_name_of_its_own() -> None:
    short = Versioned(current=1, key="v")
    assert short.stamp({"up": True}) == {"v": 1, "up": True}
    assert short.read({"v": 1, "up": True}) == {"up": True}
    with pytest.raises(UnknownVersionError, match="'v'"):
        short.read({"version": 1})


def test_a_first_version_with_no_migrations_reads_only_itself() -> None:
    only = Versioned(current=1)
    assert only.readable == (1,)


def test_the_readable_set_is_the_migration_sources_and_the_current() -> None:
    assert V2.readable == (1, 2)


def test_an_oldest_version_can_be_dropped_from_the_readable_set() -> None:
    assert Versioned(current=3, migrations={2: dict}).readable == (2, 3)


@pytest.mark.parametrize("migrations", [{1: dict}, {1: dict, 3: dict}, {3: dict}, {0: dict, 1: dict, 2: dict}])
def test_migrations_must_lead_to_the_current_version_with_no_gap(migrations: dict[int, Any]) -> None:
    with pytest.raises(ValueError, match="migration"):
        Versioned(current=3, migrations=migrations)


def test_a_current_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="current"):
        Versioned(current=0)
