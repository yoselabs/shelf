from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlite_store import Schema, Store, clear_filesystem_cache

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def schema() -> Schema:
    return Schema(
        version=2,
        ddl="""
        CREATE TABLE item (id TEXT PRIMARY KEY, value TEXT, rev INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE detail (id TEXT PRIMARY KEY, item TEXT REFERENCES item(id));
        """,
        steps={},
        name="test journal",
        revisioned=frozenset({"item"}),
        quarantine_versions=frozenset({1}),
    )


@pytest.fixture
def store(schema: Schema) -> Generator[Store]:
    clear_filesystem_cache()
    instance = Store(schema)
    yield instance
    instance.close_shared()
    clear_filesystem_cache()
