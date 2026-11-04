"""URL userinfo is removed from diagnostics without masking ordinary hosts and paths."""

from __future__ import annotations

import pytest

from git_porcelain.diagnostic_output import redact_output


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://user:pass@host/repo", "https://***@host/repo"),
        ("http://user@host/repo", "http://***@host/repo"),
        ("ssh://user@host:2222/repo", "ssh://***@host:2222/repo"),
        ("ssh://user:pass@[::1]/repo", "ssh://***@[::1]/repo"),
        ("https://user:p@ss@host/repo", "https://***@host/repo"),
        ("https://host/user@path?q=a@b", "https://host/user@path?q=a@b"),
        ("https://host/repo\nuser@host:repo", "https://host/repo\nuser@host:repo"),
        ("To 'https://u:p@host/a'\nssh://u@other/b", "To 'https://***@host/a'\nssh://***@other/b"),
    ],
)
def test_url_userinfo_is_redacted(text: str, expected: str) -> None:
    assert redact_output(text) == expected
    assert redact_output(expected) == expected
