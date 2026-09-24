# plugin-surface

**Stop caring how an app discovers and wires its plugins.** Each extension point
becomes a directory of declaration-only modules; each module exports one
`MANIFEST`. The loader walks the directory, calls each factory, and drops
anything that reports itself unavailable — so consumer code only ever sees the
plugins that actually loaded.

```python
from typing import Protocol, runtime_checkable
from plugin_surface import PluginManifest, Unavailable, load_surface


@runtime_checkable
class Provider(Protocol):
    def complete(self, prompt: str) -> str: ...


# --- in surface dir: providers/anthropic.py ---------------------------------
class Anthropic:
    def complete(self, prompt: str) -> str: ...

def _build(settings) -> Provider | Unavailable:
    if not settings.anthropic_key:
        return Unavailable("no anthropic_key")   # dropped silently, never crashes boot
    return Anthropic()

MANIFEST = PluginManifest(name="anthropic", protocol=Provider, factory=_build)
# ----------------------------------------------------------------------------

registry = load_surface("myapp.providers", Provider, settings)
# {"anthropic": <Anthropic>}  — unavailable/wrong-surface/utility modules absent
```

- **`PluginManifest`** — a frozen `(name, protocol, factory, requires=…, priority=…)`
  record, declared at the bottom of each plugin file.
- **`Unavailable(reason)`** — a factory's "not configured" return. Expected at
  boot, not an error; dropped before it reaches the registry.
- **`load_surface(path, protocol, context, *, logger=None)`** — discover +
  instantiate, returning `{name: instance}`.
- **`load_surface_sorted(...)`** — same, returning `[(name, instance), …]` by
  descending `priority` for order-sensitive surfaces.

## `describe_directory(dir, *, declaration)` — list plugins without running them

`load_surface` imports every module, so it can only list plugins you already trust.
When users drop code into a folder, you need the listing *before* that decision.
`describe_directory` parses each file and never imports it:

```python
from plugin_surface import describe_directory

# --- jobs/digest.py -----------------------------------------------------------
__myapp_job__ = {"name": "digest", "schedule": "1d"}
def run(ctx): ...
# ------------------------------------------------------------------------------

for d in describe_directory(Path("jobs"), declaration="__myapp_job__"):
    d.declaration   # {"name": "digest", "schedule": "1d"}, or None
    d.functions     # frozenset({"run"})
    d.problem       # None | "unreadable" | "unparsable" | "missing" | "not_literal" | "not_mapping"
```

- **Total per file.** A bad file comes back with `problem` set; it never raises,
  because one exception would hide every other plugin in the directory.
- **Both assignment forms.** `NAME = {...}` and `NAME: dict[str, Any] = {...}`.
- **Literals only.** A computed value is `not_literal`, never evaluated.
- Validating the literal is yours. Make that validator total too: drop a value
  you cannot use and fall back to a default, for the same whole-directory reason.

## Notes

- **Plugin files must be declaration-only.** Every module under the surface path
  is imported during discovery; a module-level side effect runs at every boot.
- **Logging is injected.** Pass `logger=` to route the `plugin_unavailable` /
  `plugin_manifest_wrong_type` diagnostics onto your app's logger (keeping its
  handler + propagation discipline); omit it for a package-local logger. Fields
  ride on `record.fields`.
- **One directory can host multiple surfaces** — manifests whose `protocol`
  doesn't match the requested one are skipped, so unrelated plugin families can
  share a folder.
- Zero dependencies; stdlib only.
