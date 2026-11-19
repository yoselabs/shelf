"""What a CLI child of an anyllm adapter inherits, and how its program is found: one place.

Both are decided from the injected ``env`` (never the process environment): the PATH searched is the mapping's, and
the child gets only the allow lists below, applied by ``child_env.build_env`` (never the whole mapping).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from child_env import NotFound, find

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

#: Proxy and certificate settings: behind a proxy or a corporate CA, a CLI with no network setting cannot reach its login server.
NETWORK_ENV = (
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "ALL_PROXY",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
)

#: What `claude` needs to authenticate, by exact name. The subscription login lives in the keychain / ``~/.claude`` (reached through
#: HOME, USER and LOGNAME, which build_env always passes). ``CLAUDE_CODE_OAUTH_TOKEN`` is the login of a machine with no keychain (a
#: container); ``CLAUDE_CONFIG_DIR`` moves the folder that holds it. The four lane variables are allowed so ClaudeHarness still refuses
#: them loudly (they move the run off the login); dropping them silently would hide that. ANTHROPIC_API_KEY and CLAUDE_CODE_SIMPLE are
#: not allowed: they would move the run to the metered API or hide the login.
CLAUDE_ENV = (
    *NETWORK_ENV,
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CONFIG_DIR",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
)

#: What `codex` needs: its login is ``$CODEX_HOME/auth.json`` (default ``~/.codex``). OPENAI_API_KEY is not allowed (never was passed).
CODEX_ENV = (*NETWORK_ENV, "CODEX_HOME")


def program(name: str, env: Mapping[str, str]) -> Path | None:
    """Where ``name`` is on ``env``'s PATH, or None; the ambient PATH is never searched."""
    try:
        return find(name, env).path
    except NotFound:
        return None
