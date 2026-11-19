# settings-base

**Stop re-deriving the same three chores in every app's `settings.py`.** The schema
(fields, defaults, which are secret) belongs to your app; the plumbing does not.

```python
from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from settings_base import SecretStrippingYamlSource, resolve_config_path, resolve_env_refs

resolve_env_refs("host=${DB_HOST}")   # "host=db.internal" (or literal on a miss)

path = resolve_config_path("MYAPP_CONFIG", Path.home() / ".myapp" / "config.yaml")
# -> Path if the file exists, else None (zero-config is the default, not an error)


class Settings(BaseSettings):
    api_key: str = ""  # secret — env only

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, *_):
        yaml_path = resolve_config_path("MYAPP_CONFIG", Path.home() / ".myapp" / "config.yaml")
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        if yaml_path is not None:
            sources.append(
                SecretStrippingYamlSource(settings_cls, exclude={"api_key"}, yaml_file=yaml_path)
            )
        return tuple(sources)
```

- **`resolve_env_refs`** — expand `${VAR}` inside a loaded string, leaving the literal
  in place on a miss.
- **`resolve_config_path`** — resolve an optional config file from an env override or a
  default path; `None` when nothing is set and the default is missing. A *set* override that is not
  a file raises `ConfigOverrideError` (a `ValueError`); it never silently disables config.
- **`SecretStrippingYamlSource`** — drop caller-named secret fields from the YAML so
  they must come from the environment.

## Surface

- `resolve_env_refs(value: str, *, env: Mapping | None = None) -> str`
- `resolve_config_path(env_var: str, default: Path, *, env: Mapping | None = None) -> Path | None`
- `ConfigOverrideError(ValueError)`
- `SecretStrippingYamlSource(settings_cls, *, exclude, yaml_file)`
