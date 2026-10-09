"""Names a program mints for files, and names that hold a secret by convention."""

from __future__ import annotations

import fnmatch
import re
from pathlib import PurePosixPath
from typing import cast

from anyascii import anyascii

#: Lowercase letters, digits, hyphens, nothing else.
_UNSAFE = re.compile(r"[^a-z0-9]+")

#: Long enough to stay readable in a file listing, short enough that a path with several
#: nested slugs does not approach a filesystem limit.
DEFAULT_SLUG_LENGTH = 48


def slugify(text: str, *, max_length: int = DEFAULT_SLUG_LENGTH, fallback: str = "untitled") -> str:
    """``text`` as a lowercase hyphenated slug; ``fallback`` when nothing survives.

    Transliterated first (anyascii), so ``Проект`` is ``proekt`` and not the fallback every
    non-Latin title used to share. anyascii is the identity on ASCII, so an ASCII slug is
    what ``[^a-z0-9]+`` alone gives. Truncation happens after collapsing: ``max_length``
    bounds the result, and a cut mid-word leaves no trailing hyphen.
    """
    ascii_text = cast("str", anyascii(text))  # anyascii ships no annotations
    collapsed = _UNSAFE.sub("-", ascii_text.lower()).strip("-")
    return collapsed[:max_length].rstrip("-") or fallback


#: Basename patterns, lowercase, of files that hold a credential because of what they are
#: (dotenv, keys, cloud and package-registry credentials, SSH private keys) — never a file
#: whose name merely mentions a secret: ``token.png`` and ``secret-plan.md`` are not here.
SECRET_NAME_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    ".envrc",
    "*.pem",
    "*.key",
    "credentials",
    "credentials.json",
    "client_secret*.json",
    ".npmrc",
    ".pypirc",
    ".netrc",
    ".git-credentials",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ecdsa_sk",
    "id_ed25519",
    "id_ed25519_sk",
)


def secret_pattern(path: str) -> str | None:
    """The pattern ``path``'s file name matches, case-insensitively, or ``None``.

    Only the basename is matched, in any folder; ``/`` is the separator.
    """
    name = PurePosixPath(path).name.lower()
    return next((pattern for pattern in SECRET_NAME_PATTERNS if fnmatch.fnmatchcase(name, pattern)), None)
