"""One canonical JSON hash convention: sorted keys, UTF-8, refusing what JSON cannot say."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from content_digest import digest, digest_bytes, digest_file, digest_text

if TYPE_CHECKING:
    from pathlib import Path


def test_key_order_does_not_matter() -> None:
    assert digest({"a": 1, "b": [1, 2]}) == digest({"b": [1, 2], "a": 1})


def test_list_order_matters() -> None:
    assert digest([1, 2]) != digest([2, 1])


def test_default_is_twelve_hex_characters_and_length_is_adjustable() -> None:
    full = digest({"a": 1}, length=64)
    assert len(digest({"a": 1})) == 12
    assert len(full) == 64
    assert full.startswith(digest({"a": 1}))


def test_value_is_compact_sorted_utf8_json() -> None:
    expected = hashlib.sha256('{"a":"é","b":1}'.encode()).hexdigest()[:12]
    assert digest({"b": 1, "a": "é"}) == expected


def test_a_text_and_its_json_string_differ_but_digest_text_is_plain_sha256() -> None:
    assert digest_text("é") == hashlib.sha256("é".encode()).hexdigest()[:12]
    assert digest("é") != digest_text("é")


def test_digest_text_length() -> None:
    assert digest_text("x", length=64) == hashlib.sha256(b"x").hexdigest()


@pytest.mark.parametrize("bad", [datetime(2026, 1, 1, tzinfo=UTC), {1, 2}, b"x", object(), float("nan"), float("inf")])
def test_refuses_what_json_cannot_say(bad: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        digest({"k": bad})


def test_a_datetime_and_its_string_never_hash_alike() -> None:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(TypeError):
        digest(when)
    assert digest(str(when)) != digest(when.isoformat() + "x")


def test_refuses_non_string_keys_instead_of_merging_them_with_strings() -> None:
    with pytest.raises(TypeError, match="key"):
        digest({1: "a"})


@pytest.mark.parametrize("length", [0, -1, 65])
def test_refuses_a_length_outside_one_to_sixty_four(length: int) -> None:
    with pytest.raises(ValueError, match="length"):
        digest({}, length=length)
    with pytest.raises(ValueError, match="length"):
        digest_text("", length=length)


def test_digest_file_matches_hashlib_on_a_file_larger_than_one_chunk(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(bytes(range(256)) * 20_000)  # 5 MB: several chunks
    golden = hashlib.sha256(audio.read_bytes()).hexdigest()
    assert digest_file(audio, length=64) == golden  # the full sha256 any-speech stores as audio_sha256
    assert digest_file(audio) == golden[:12]


def test_digest_file_of_an_empty_file_is_the_sha256_of_nothing(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    assert digest_file(empty, length=64) == hashlib.sha256(b"").hexdigest()


def test_digest_file_refuses_a_bad_length(tmp_path: Path) -> None:
    (tmp_path / "f").write_bytes(b"x")
    with pytest.raises(ValueError, match="length"):
        digest_file(tmp_path / "f", length=65)


def test_digest_file_of_a_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        digest_file(tmp_path / "nope")


def test_digest_bytes_is_sha256_of_the_bytes_as_given() -> None:
    data = b"\x00\xff raw"
    assert digest_bytes(data, length=64) == hashlib.sha256(data).hexdigest()
    assert digest_bytes("é".encode()) == digest_text("é")
