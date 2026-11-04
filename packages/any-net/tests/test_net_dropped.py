from __future__ import annotations

import pytest

from any_net import looks_dropped


@pytest.mark.parametrize(
    "text",
    [
        "Error: getaddrinfo ENOTFOUND api.openai.com",
        "read ECONNRESET",
        "curl: (6) Could not resolve host: x",
        "error sending request for url (https://x)",
        "Connection timed out",
        "socket hang up",
        "TLS handshake failed",
        "stream disconnected before completion",
    ],
)
def test_network_errors_are_drops(text: str) -> None:
    assert looks_dropped(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "the answer is 42",
        "stream disconnected: hit max_output_tokens limit",
    ],
)
def test_other_text_is_not_a_drop(text: str | None) -> None:
    assert not looks_dropped(text)
