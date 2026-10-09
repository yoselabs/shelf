"""secret_pattern — a file that holds a credential by convention, matched by its basename."""

from __future__ import annotations

import pytest
from any_file import SECRET_NAME_PATTERNS, secret_pattern


@pytest.mark.parametrize(
    ("path", "pattern"),
    [
        (".env", ".env"),
        ("app/.env.production", ".env.*"),
        ("deep/folder/.ENVRC", ".envrc"),
        ("certs/server.pem", "*.pem"),
        ("Private.KEY", "*.key"),
        ("credentials", "credentials"),
        ("gcp/credentials.json", "credentials.json"),
        ("client_secret_123.apps.json", "client_secret*.json"),
        (".npmrc", ".npmrc"),
        ("~/.netrc", ".netrc"),
        (".ssh/id_ed25519", "id_ed25519"),
    ],
)
def test_a_secret_file_names_its_pattern(path: str, pattern: str) -> None:
    assert secret_pattern(path) == pattern


@pytest.mark.parametrize(
    "path",
    ["token.png", "secret-plan.md", "notes/credentials-howto.md", "id_rsa.pub", ".env-notes/readme.md", "environment.md", "keys.md"],
)
def test_a_name_that_only_mentions_a_secret_is_not_one(path: str) -> None:
    assert secret_pattern(path) is None


def test_the_patterns_are_lowercase_basenames() -> None:
    assert all(p == p.lower() and "/" not in p for p in SECRET_NAME_PATTERNS)
