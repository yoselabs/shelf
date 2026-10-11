# Per-repo toolchain installer: mise vs proto vs aqua (trial 2026-10-11)

One Sonnet pass, hands-on on scratch clones of the shelf and lifesim (macOS arm64; mise 2026.10.8,
proto 0.63.1, aqua 2.64.0). Owner shortlist; devbox, flox, devenv, pixi and asdf were ruled out before
the trial. Configs that worked: `toolchain-trial/shelf.mise.toml`, `toolchain-trial/lifesim.mise.toml`.

## Verdict

mise: `mise.toml` plus a committed `mise.lock`, installed with `mise install --locked`. It uses only the
tool pins: mise's tasks and env features stay unused, because just runs the tasks.

## Comparison (tested unless marked read)

| criterion | mise | proto | aqua |
|---|---|---|---|
| uv, just, prek, bd | ✅ registry aliases; bd via `github:gastownhall/beads` with `bin = "bd"` | ⚠️ uv built in; just via a third-party wasm plugin; prek and bd need hand-written plugins | ✅ all in the standard registry |
| .NET SDK | ✅ core plugin, reads `global.json` (`idiomatic_version_file_enable_tools = ["dotnet"]`), no second pin | ⚠️ third-party plugin, cannot parse global.json | ❌ in no registry; needs a local `http` package |
| Godot 4.x .NET | ⚠️ `github:godotengine/godot` with a per-platform `asset_pattern` (mono assets); macOS tested | ⚠️ hand-written plugin | ⚠️ local registry plus a policy file |
| reads existing pins | ✅ global.json; leaves Python to uv's `.python-version` | ❌ | ❌ every pin duplicated |
| lockfile and checksums | ✅ per-platform sha256; a tampered checksum fails `--locked`; bd records GitHub attestations; dotnet and Godot get no checksum | ⚠️ lockfile flagged unstable, records only fresh installs | ✅ checksums plus attestation verification |
| agent experience | ✅ 1.2 s cold with the lock, 13.7 s without; no prompt; `mise exec` needs no shell activation | ⚠️ `proto trust` required in a fresh clone, or plugins are skipped with only a warning | ⚠️ 40 s cold; custom registries need a policy file; `just` never passed the policy |
| maturity (read, 2026-10-11) | 34.9k stars, active; one maintainer has ~63% of commits | 1.4k stars; ~92% one maintainer | 1.9k stars; 186 open issues |

## Findings that carry into blueprint

- Unauthenticated GitHub API calls are capped at 60 an hour; the trial hit it. Agents and CI need
  `GITHUB_TOKEN`/`MISE_GITHUB_TOKEN`, or install from the lock so no API call is made.
- uv's version is written twice (`[tool.uv] required-version` floor and mise's exact pin): a check must
  compare them.
- The Godot editor pin must equal `Godot.NET.Sdk/x.y.z` in the csproj.
- lifesim's justfile defaults `GODOT` to an /Applications path; under mise it should take `$(which godot)`.
- lifesim's branches already disagree on `global.json` (main 10.0.401 latestPatch, wip/bootstrap
  10.0.301 latestFeature).
- bd versions drifted across machines (Mac 1.1.2, devbox 1.3.1) and the newer one migrated the shared
  Dolt schema: the case for pinning bd exactly.

## How blueprint would check (no network)

1. Parse `mise.toml`; map each profile role to a tool key; dotnet is satisfied by the idiomatic read of
   `global.json` (no `dotnet` key allowed when global.json exists); no `python` key when `.python-version`
   exists (uv owns Python).
2. Exact versions only: fail `latest`, ranges, branches.
3. `mise.lock` present with a checksum per tool; dotnet and Godot are a documented exception.
4. Cross-file agreement: uv pin satisfies `required-version`; Godot pin equals the csproj SDK version.
5. Audit-only: each installed tool's version equals its pin (bd first).

## Refused

- aqua: no .NET, no mono Godot without a local registry and policy; every pin duplicated. Fallback only
  if attestation verification becomes mandatory.
- proto: third-party dotnet plugin that cannot read global.json; hand-written plugins; unstable lock;
  the trust step breaks fresh clones.
- Native pins only (uv, global.json, csproj): leaves just, prek, bd and the Godot editor unpinned.
- `pipx:rust-just` through mise: no per-platform checksum, and the gate runner then depends on Python.
