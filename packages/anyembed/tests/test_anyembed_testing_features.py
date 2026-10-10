"""anyembed.testing, stated as Gherkin."""

from __future__ import annotations

import math

import pytest
from anyembed import Embedder
from anyembed.testing import HashEmbedder
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/hash_embedder.feature")


@pytest.fixture
def vectors() -> list[list[float]]:
    return []


@pytest.fixture
def embedder() -> list[HashEmbedder]:
    return []


@given(parsers.parse("a hash embedder of {dim:d} dimensions"))
def _embedder(embedder: list[HashEmbedder], dim: int) -> None:
    embedder.append(HashEmbedder(dim))


@when(parsers.parse('"{a}" and "{b}" are embedded as documents'))
def _documents(embedder: list[HashEmbedder], vectors: list[list[float]], a: str, b: str) -> None:
    vectors.extend(embedder[0].embed_documents([a, b]))


@when(parsers.parse('"{text}" is embedded as a document and as a query'))
def _both(embedder: list[HashEmbedder], vectors: list[list[float]], text: str) -> None:
    vectors.extend([*embedder[0].embed_documents([text]), embedder[0].embed_query(text)])


@then(parsers.parse("each vector has {dim:d} numbers and unit length"))
def _shape(vectors: list[list[float]], dim: int) -> None:
    for vector in vectors:
        assert len(vector) == dim
        assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0)


@then(parsers.re(r"the two vectors are (?P<same>equal|different)"))
def _same(vectors: list[list[float]], same: str) -> None:
    assert (vectors[0] == vectors[1]) is (same == "equal")


@then(parsers.parse('it satisfies the Embedder protocol with model id "{model_id}"'))
def _protocol(embedder: list[HashEmbedder], model_id: str) -> None:
    assert isinstance(embedder[0], Embedder)
    assert embedder[0].model_id == model_id
