"""settings-base — the generic env/YAML plumbing behind a pydantic-settings config.

**Stop re-deriving the same three chores in every app's ``settings.py``.** The
schema (which fields, which defaults, which are secret) belongs to the app; the
*mechanism* does not:

- :func:`resolve_env_refs` — expand ``${VAR}`` references inside a loaded string,
  leaving the literal in place on a miss (so a YAML value can reference an env
  secret without templating the whole file).
- :func:`resolve_config_path` — resolve an optional config file from an env
  override or a default path, returning ``None`` unless the file actually exists
  (so a zero-config run is the expected default, not an error).
- :class:`SecretStrippingYamlSource` — a pydantic-settings YAML source that drops
  caller-named secret fields from the loaded document, forcing those to come from
  the environment only.

Domain-free: the field names, the secret set, and the path defaults are all
caller-supplied. This package knows *how* to plumb, never *what* is being
configured.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic_settings import YamlConfigSettingsSource

if TYPE_CHECKING:
    from collections.abc import Collection

    from pydantic_settings import BaseSettings

__all__ = ("SecretStrippingYamlSource", "resolve_config_path", "resolve_env_refs")

_ENV_REF_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def resolve_env_refs(value: str) -> str:
    """Replace ``${VAR}`` with ``os.environ[VAR]``; leave the literal on a miss.

    Args:
        value: A string that may contain one or more ``${VAR}`` references.

    Returns:
        ``value`` with every resolvable reference expanded; unresolved
        references are left verbatim.
    """

    def _sub(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), match.group(0))

    return _ENV_REF_RE.sub(_sub, value)


def resolve_config_path(env_var: str, default: Path) -> Path | None:
    """Resolve an optional config file from an env override or a default path.

    Args:
        env_var: Name of the environment variable that, when set, overrides the
            config location (``~`` is expanded).
        default: The fallback path consulted when ``env_var`` is unset.

    Returns:
        The resolved path if the chosen candidate is an existing file, else
        ``None``.
    """
    override = os.environ.get(env_var)
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None
    return default if default.is_file() else None


class SecretStrippingYamlSource(YamlConfigSettingsSource):
    """A YAML settings source that drops caller-named secret fields.

    Any field listed in ``exclude`` is removed from the loaded YAML document, so
    those values must be supplied via the environment (or another source) rather
    than committed to a config file.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        *,
        exclude: frozenset[str] | Collection[str],
        yaml_file: Path | str,
    ) -> None:
        """Initialize the source.

        Args:
            settings_cls: The ``BaseSettings`` subclass being loaded.
            exclude: Field names to strip from the loaded YAML (the secrets).
            yaml_file: Path to the YAML document.
        """
        self._exclude = frozenset(exclude)
        super().__init__(settings_cls, yaml_file=yaml_file)

    def __call__(self) -> dict[str, Any]:
        """Load the YAML document and remove every excluded (secret) field."""
        data = super().__call__()
        for key in self._exclude:
            data.pop(key, None)
        return data
