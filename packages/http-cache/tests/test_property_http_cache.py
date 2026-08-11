"""Property-based tests, additive on top of the round-trip example suite.

See docs/runbooks/property-based-testing.md. Generalizes variant isolation beyond
the two hand-picked profiles in the example suite, and adds two properties the
example suite doesn't state: content_hash is independently verifiable (not just
"populated"), and the ttl_s > 0 / <= 0 boundary is exact for arbitrary values, not
just the one -1 example.
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path

from http_cache import HttpCache
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

_IO_SETTINGS = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])

_VARIANT = st.text(alphabet=st.characters(categories=["L", "N"]), min_size=1, max_size=8)
_BODY = st.binary(max_size=200)


async def _store(cache: HttpCache, url: str, variant: str, body: bytes, ttl_s: int) -> None:
    await cache.put(
        url,
        variant,
        etag=None,
        last_modified=None,
        status_code=200,
        content_type=None,
        body=body,
        ttl_s=ttl_s,
    )


@given(variant_bodies=st.dictionaries(_VARIANT, _BODY, min_size=1, max_size=6))
@_IO_SETTINGS
def test_property_variants_of_the_same_url_never_cross_contaminate(variant_bodies: dict[str, bytes]) -> None:
    """For any generated set of variants under ONE url, each variant's get()
    returns exactly the body stored under that variant — never another's.
    """

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            async with HttpCache(Path(tmp) / "c.sqlite") as cache:
                for variant, body in variant_bodies.items():
                    await _store(cache, "https://x/", variant, body, ttl_s=900)
                for variant, body in variant_bodies.items():
                    row = await cache.get("https://x/", variant)
                    assert row is not None
                    assert row.body == body

    asyncio.run(run())


@given(body=_BODY)
@_IO_SETTINGS
def test_property_content_hash_is_independently_verifiable(body: bytes) -> None:
    """content_hash is populated (already tested) — this checks it's the RIGHT
    hash, recomputed independently rather than trusting the stored value.
    """

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            async with HttpCache(Path(tmp) / "c.sqlite") as cache:
                await _store(cache, "https://x/", "", body, ttl_s=900)
                row = await cache.get("https://x/")
                assert row is not None
                assert row.content_hash == hashlib.sha256(body).hexdigest()

    asyncio.run(run())


@given(ttl_s=st.integers(min_value=-1000, max_value=0))
@_IO_SETTINGS
def test_property_non_positive_ttl_is_never_retrievable(ttl_s: int) -> None:
    """Generalizes test_expired_row_is_not_returned (fixed at ttl_s=-1) across the
    whole non-positive range, including the exact boundary ttl_s=0.
    """

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            async with HttpCache(Path(tmp) / "c.sqlite") as cache:
                await _store(cache, "https://x/", "", b"body", ttl_s=ttl_s)
                assert await cache.get("https://x/") is None

    asyncio.run(run())


@given(ttl_s=st.integers(min_value=1, max_value=100_000))
@_IO_SETTINGS
def test_property_positive_ttl_is_retrievable_immediately(ttl_s: int) -> None:
    """The complement of the property above, across the positive range."""

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            async with HttpCache(Path(tmp) / "c.sqlite") as cache:
                await _store(cache, "https://x/", "", b"body", ttl_s=ttl_s)
                assert await cache.get("https://x/") is not None

    asyncio.run(run())
