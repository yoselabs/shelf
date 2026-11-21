"""child-env — the environment a child agent process should get.

**Stop copying the env scrub.** A Claude session (desktop app, CLI, plugins) exports ``CLAUDE_*``,
``ANTHROPIC_*``, ``MCP_*``, ``OTEL_*`` and friends to everything it launches; a standalone ``claude`` or
``codex`` started with them misbehaves (nested-session errors, a keychain login that looks expired, a staging
login server). A worker should also not inherit the launcher's tokens and keys. ``scrub(env)`` returns a new
dict without those; ``keep`` rescues names, ``drop`` removes more.

``without_venv(env)`` strips (compose it: ``scrub(without_venv(env))``) an active Python virtualenv: the
interpreter variables it sets, and its ``bin`` folder in ``PATH``. Nothing else is touched.

``build_env(env, allow=, extra=)`` is the allowlist form: only ``DEFAULT_INHERIT`` and ``allow`` names pass, secrets
never do unless named exactly. ``find(name, env, extra_dirs)`` finds the program the child runs (see ``exe``): its
PATH is the injected ``env``'s, and a miss raises ``NotFound`` instead of returning the bare name.

Pure: the input mapping is never mutated and ``os.environ`` is never read; the edge passes it in.

An entry in ``keep`` / ``drop`` is an exact variable name, or a prefix when it ends with ``*``
(``"MCP_*"``). Precedence: ``drop`` beats everything; ``keep`` beats the defaults.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from child_env.exe import Exe, NotFound, find

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

#: Agent-session prefixes: everything a Claude / Codex session exports to its children.
APP_PREFIXES: tuple[str, ...] = ("CLAUDE_", "ANTHROPIC_", "DELEGATE_", "MCP_", "OTEL_", "CODEX_COMPANION")
#: Agent-session variables named exactly (no shared prefix).
APP_NAMES: tuple[str, ...] = (
    "CLAUDECODE",
    "AI_AGENT",
    "API_TIMEOUT_MS",
    "BAGGAGE",
    "DISABLE_MICROCOMPACT",
    "DISABLE_AUTOUPDATER",
    "USE_LOCAL_OAUTH",
    "USE_STAGING_OAUTH",
)
#: Credential variables by prefix (cloud and git-host credentials).
CREDENTIAL_PREFIXES: tuple[str, ...] = ("AWS_", "GH_", "GITHUB_")
#: Credential variables named exactly (the ssh agent socket is a credential: it signs as the user).
CREDENTIAL_NAMES: tuple[str, ...] = ("SSH_AUTH_SOCK",)
#: Credential-looking words anywhere in a name, compared upper-case (``api_key`` and ``APIKEY`` both match).
CREDENTIAL_MARKERS: tuple[str, ...] = (
    "TOKEN",
    "SECRET",
    "PASSW",
    "CREDENTIAL",
    "API_KEY",
    "APIKEY",
    "ACCESS_KEY",
    "ACCESSKEY",
    "PRIVATE_KEY",
    "PRIVATEKEY",
)
#: Variables an active Python virtualenv (or a launcher that runs inside one) sets; a child that inherits them runs in our venv.
VENV_NAMES: tuple[str, ...] = (
    "VIRTUAL_ENV",
    "VIRTUAL_ENV_PROMPT",
    "PYTHONHOME",
    "__PYVENV_LAUNCHER__",
    "PYTHONEXECUTABLE",
)
#: What a child inherits from ``build_env`` by default: the user's place and locale, nothing of the app's own.
DEFAULT_INHERIT: tuple[str, ...] = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_*", "TERM", "TMPDIR", "TZ", "XDG_*")


def _matches(name: str, patterns: Iterable[str]) -> bool:
    return any(name.startswith(p[:-1]) if p.endswith("*") else name == p for p in patterns)


def _default_drop(name: str) -> bool:
    upper = name.upper()
    return (
        name.startswith(APP_PREFIXES)
        or name in APP_NAMES
        or upper.startswith(CREDENTIAL_PREFIXES)
        or upper in CREDENTIAL_NAMES
        or any(m in upper for m in CREDENTIAL_MARKERS)
    )


def without_venv(env: Mapping[str, str]) -> dict[str, str]:
    """A new dict: ``env`` without the active virtualenv.

    Removes ``VENV_NAMES`` and, when ``VIRTUAL_ENV`` is set, the entry ``$VIRTUAL_ENV/bin`` from ``PATH`` (an exact
    match; other entries, their order and an empty PATH entry stay). Without ``VIRTUAL_ENV`` the PATH is untouched.
    """
    venv = env.get("VIRTUAL_ENV")
    out = {k: v for k, v in env.items() if k not in VENV_NAMES}
    if venv and "PATH" in out:
        bin_dir = os.path.join(venv, "bin")  # noqa: PTH118 - string-exact join, as the PATH entry is compared as text
        out["PATH"] = os.pathsep.join(p for p in out["PATH"].split(os.pathsep) if p != bin_dir)
    return out


def scrub(
    env: Mapping[str, str],
    *,
    keep: Iterable[str] = (),
    drop: Iterable[str] = (),
) -> dict[str, str]:
    """A new dict: ``env`` without agent-session and credential variables.

    ``keep`` names (or ``PREFIX*``) survive the default rules; ``drop`` names (or ``PREFIX*``) are removed
    even when they would otherwise stay, and win over ``keep``. The virtualenv is not touched: call
    ``scrub(without_venv(env))`` to strip it too (done first, so it wins over ``keep``).
    """
    keep_, drop_ = tuple(keep), tuple(drop)
    return {k: v for k, v in env.items() if not _matches(k, drop_) and (_matches(k, keep_) or not _default_drop(k))}


def build_env(
    env: Mapping[str, str],
    *,
    allow: Iterable[str] = (),
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """A new dict holding only the ``DEFAULT_INHERIT`` names and ``allow`` names (exact, or ``PREFIX*``) of ``env``, then ``extra``.

    The allowlist is the door: nothing else of ``env`` reaches the child, so a whole ``os.environ`` is never passed.
    Secrets (the same rules as ``scrub``) are dropped even under an allowed prefix; one passes only when its exact
    name is in ``allow``. ``extra`` is set last and wins.
    """
    allow_ = tuple(allow)
    exact = {a for a in allow_ if not a.endswith("*")}
    out = {k: v for k, v in env.items() if k in exact or (_matches(k, (*DEFAULT_INHERIT, *allow_)) and not _default_drop(k))}
    return {**out, **(extra or {})}


__all__ = [
    "APP_NAMES",
    "APP_PREFIXES",
    "CREDENTIAL_MARKERS",
    "CREDENTIAL_NAMES",
    "CREDENTIAL_PREFIXES",
    "DEFAULT_INHERIT",
    "VENV_NAMES",
    "Exe",
    "NotFound",
    "build_env",
    "find",
    "scrub",
    "without_venv",
]
