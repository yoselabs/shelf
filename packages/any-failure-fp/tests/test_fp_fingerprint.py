from __future__ import annotations

import re

from any_failure_fp import fingerprint, head

# A host's own id shape: a prefix, or any hyphenated token holding a digit.
BEAD = re.compile(
    r"\b(?:(?:tl|lifesim|task|bead|fld)[.-][a-z0-9]+(?:[.-][a-z0-9]+)*|(?=[a-z0-9.-]*\d)[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+)\b",
    re.IGNORECASE,
)
IDS = {"bead": BEAD}


def test_volatile_ids_paths_numbers_and_quotes_do_not_change_it() -> None:
    a = fingerprint("failed: bead tl-19i on /Users/me/repo/src/file.py exit 1 after 2.8 h: `boom`", ids=IDS)
    b = fingerprint("FAILED: bead lifesim-d5f.46 on /home/other/tree/a/b.py exit 127 after 14 h: `bang`", ids=IDS)
    assert a == b
    assert "<bead>" in a
    assert "<path>" in a
    assert "<quoted>" in a


def test_session_sha_and_uuid_are_volatile() -> None:
    one = fingerprint("thread ref-write failed at 1234abc after ses_123 on 123e4567-e89b-12d3-a456-426614174000", ids=IDS)
    two = fingerprint("thread ref-review failed at deadbeef after ses_999 on 00000000-0000-0000-0000-000000000000", ids=IDS)
    assert one == two


def test_distinct_failures_stay_distinct() -> None:
    assert fingerprint("missing recipe: just unity-tests") != fingerprint("compile error in Assets/Player.cs")
    assert fingerprint("no lane for write") != fingerprint("review sent it back: unmet acceptance")


def test_letter_only_host_ids_are_volatile() -> None:
    a = fingerprint("failed: bead tl-fsj cannot resume", ids=IDS)
    assert a == fingerprint("failed: bead tl-xyz cannot resume", ids=IDS)
    assert "tl-fsj" not in a


def test_without_ids_host_tokens_stay() -> None:
    assert "tl-fsj" in fingerprint("bead tl-fsj failed")


def test_relative_and_windows_paths_are_volatile() -> None:
    a = fingerprint("compile error in Assets/Player.cs")
    assert a == fingerprint(r"compile error in Assets\Enemy.cs")
    assert a == fingerprint("compile error in /repo/Assets/Other.cs")
    assert "<path>" in a


def test_digits_in_paths_and_sessions_are_not_ids() -> None:
    one = fingerprint("compile error in Assets/Player2.cs from thread-123", ids=IDS)
    assert one == fingerprint("compile error in Assets/Player.cs from thread-abc", ids=IDS)
    assert "<path>" in one
    assert "<session>" in one
    assert "<bead>" not in one


def test_whole_paths_win_over_embedded_hex_and_sessions() -> None:
    one = fingerprint("failed in thread-1234abc from /repo/thread-deadbeef/Assets/Player.cs", ids=IDS)
    two = fingerprint("failed in thread-9999fff from C:\\repo\\thread-cafebabe\\Assets\\Enemy.cs", ids=IDS)
    assert one == two


def test_ansi_urls_and_braces_are_dropped() -> None:
    a = fingerprint('\x1b[31mfetch https://a.example/x?y=1 failed {"code": 5}\x1b[0m')
    assert a == fingerprint('fetch http://b.example/z failed {"code": 9}')
    assert "<url>" in a
    assert "<json>" in a


def test_empty_when_nothing_to_say() -> None:
    assert fingerprint("") == ""
    assert fingerprint("  \n ") == ""
    assert fingerprint(None) == ""
    assert fingerprint(" : ; ") == ""


def test_a_long_tail_gets_a_hash_and_head_drops_it() -> None:
    long_a = "x" * 200 + " alpha"
    long_b = "x" * 200 + " beta"
    fa, fb = fingerprint(long_a), fingerprint(long_b)
    assert len(fa) == 121
    assert fa != fb
    assert head(fa) == head(fb)
    assert re.search(r"#[0-9a-f]{8}$", fa)
    assert head(fa) == "x" * 112


def test_tail_is_tunable() -> None:
    assert len(fingerprint("word " * 40, tail=40)) == 41
    assert fingerprint("short", tail=40) == "short"


def test_head_of_a_short_fingerprint_is_itself() -> None:
    assert head("compile error") == "compile error"
