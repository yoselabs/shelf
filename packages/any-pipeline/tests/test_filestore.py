"""FileStore: the Store contract on a directory, kept across instances, safe for any key."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from any_pipeline import FileStore, Limit, Persistent, Store, run

if TYPE_CHECKING:
    from pathlib import Path

L = Limit(calls=1, seconds=5, tries=1)

HOSTILE = [
    "plain",
    "a/b/c",
    "../../escape",
    "..",
    ".",
    "/abs/path",
    "naïve/日本語/😀",
    "x" * 5000,
    "with space and\nnewline",
    "",
    "CON:aux?*",
]


def files_under(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


async def test_a_missing_key_is_none_and_the_directory_is_not_created_by_a_read(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "cache")
    assert await store.get("k") is None
    assert not (tmp_path / "cache").exists()


async def test_the_directory_is_created_on_the_first_put(tmp_path: Path) -> None:
    store: Store[str] = FileStore(tmp_path / "a" / "b")
    await store.put("k", "v")
    assert await store.get("k") == "v"


@pytest.mark.parametrize("key", HOSTILE, ids=[f"key{i}" for i in range(len(HOSTILE))])
async def test_any_key_round_trips_and_stays_inside_the_directory(tmp_path: Path, key: str) -> None:
    root = tmp_path / "cache"
    store = FileStore(root)
    await store.put(key, "value")
    assert await store.get(key) == "value"
    written = files_under(tmp_path)
    assert len(written) == 1 and written[0].parent == root and len(written[0].name) < 200


async def test_distinct_keys_never_share_a_file(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    keys = ["a/b", "a_b", "a b", "a-b", "A/B", "a/b "]
    for i, key in enumerate(keys):
        await store.put(key, str(i))
    assert [await store.get(k) for k in keys] == [str(i) for i in range(len(keys))]


async def test_empty_and_awkward_values_round_trip_exactly(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    for i, value in enumerate(["", "a\rb", "a\r\nb", "日本語", "x" * 100_000]):
        await store.put(f"k{i}", value)
        assert await store.get(f"k{i}") == value


async def test_a_put_replaces_and_leaves_no_temp_file(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    await store.put("k", "one")
    await store.put("k", "two")
    assert await store.get("k") == "two"
    assert len(files_under(tmp_path)) == 1


async def test_a_persistent_stage_is_skipped_by_a_second_run_over_a_new_store_instance(tmp_path: Path) -> None:
    calls: list[str] = []

    async def costly(name: str) -> str:
        calls.append(name)
        return name.upper()

    def stage() -> Persistent[str, str]:
        return Persistent("costly", costly, L, key=lambda n: f"costly/{n}", store=FileStore(tmp_path))

    first = await run(stage(), ["a/b"], key=str, workers=1)
    second = await run(stage(), ["a/b"], key=str, workers=1)
    assert calls == ["a/b"] and second.outcomes == first.outcomes
    assert [(r.skipped, r.tries) for r in second.records] == [(True, 0)]
