# Godot 4.x (.NET / C#) framework profile: research

Date: 2026-10-10. Method: GitHub API (releases, pushes) plus READMEs and godot-docs, read in one pass. Everything is
"one pass, not cross-checked" unless stated. Consumer: lifesim (Godot 4.7.2 .NET in `src/Game.Godot`, engine-free `Sim.*`).
Output profile: `packages/blueprint/src/blueprint/profiles/frameworks/godot.toml`.

Findings about lifesim itself (read-only inspection):
- `global.json` pins only the .NET SDK (10.0.301); it does NOT pin Godot.NET.Sdk. The 4.7.2 pin lives in `src/Game.Godot/Game.Godot.csproj` (`Sdk="Godot.NET.Sdk/4.7.2"`) and `project.godot` (`"4.7"`). The strategy doc says global.json pins it; the repo does not.
- No `.gitattributes`. `.gitignore` has `.godot/`. `Main.cs.uid` is committed (good). No `export_presets.cfg`, no CI, no GDScript.
- `make godot-import` runs `--headless --import` then `--build-solutions --quit`, but sits outside `make check`.
- `ForbidGodotInSim` target in `Directory.Build.props` already enforces engine-free Sim.*.
- Sim tests: `tests/Sim.*` only; no view tests.

## Roles

| Role | Tool | Why | Evidence (date) | Verification signal | Verdict |
|---|---|---|---|---|---|
| GDScript lint/format | gdtoolkit (gdlint, gdformat) | The established linter/formatter | github.com/Scony/godot-gdscript-toolkit, 4.5.0 released 2025-10-09; no release in 12 months (stale?) | `.gd` files exist AND Makefile has `gdlint` | untested for 4.7 syntax; lifesim has no `.gd`: `na` |
| GDScript formatter (alt) | GDQuest GDScript-formatter | Newer, fast, actively released | github.com/GDQuest/GDScript-formatter, 0.27.0 released 2026-09-25 | Makefile has `gdscript-formatter` | untested (pre-1.0, formatter only, no linter) |
| C# in Godot | Godot.NET.Sdk (pinned exact) + built-in Godot source generators | Sdk ships the generators; the editor rewrites csproj if Sdk/TFM missing | godotengine/godot 4.7.2-stable, 2026-08-18; lifesim csproj comment | csproj `Godot.NET.Sdk/<x.y.z>`; Directory.Build.props `TreatWarningsAsErrors`, `Nullable enable` (dotnet.toml covers) | ✅ adopt (already) |
| C# analyzers | .NET analyzers latest-all + Meziantou/Roslynator/Sonar; Godot-specific suppressions scoped in .editorconfig | Godot naming (`_Ready`) trips CA1707 etc. | lifesim `.editorconfig` section `[src/Game.Godot/**.cs]` | `.editorconfig` has a Game.Godot scope; `dotnet build -warnaserror` | ✅ adopt (already) |
| Formatter C# | CSharpier 1.3.0 | Layout owned by one tool | lifesim `.config/dotnet-tools.json` | `csharpier check` in Makefile | ✅ adopt (already) |
| Headless build/import | `godot --headless --path <proj> --import` then `--build-solutions --quit` | First import generates `.godot/` + the C# glue; needed before any in-engine run | godot-ci 4.7.2-stable released 2026-08-18 uses these; lifesim Makefile target | Makefile recipe containing `--build-solutions` and `--headless` reached by `make check` | ✅ adopt; gap: lifesim keeps it outside `check` (a machine without the app skips it) |
| Engine pin | csproj `Godot.NET.Sdk/x.y.z` (single source); CI reads it | Godot has no version file; setup-godot's README says version may be "global.json" (reads msbuild-sdks) | chickensoft-games/setup-godot v2.4.3, 2026-10-01 | regex `Godot.NET.Sdk/\d+\.\d+\.\d+` in a `*.csproj`; equal to `config/features` major.minor in project.godot | ✅ adopt; consider `msbuild-sdks` in global.json as the one source (untested) |
| CI action | chickensoft-games/setup-godot@v2 (`use-dotnet`, `include-templates`, cached) | Installs Godot .NET on all 3 OS runners | same README, v2.4.3 2026-10-01, pushed same day | workflow contains `setup-godot` and the make target | ✅ adopt |
| CI image (alt) | abarichello/godot-ci Docker | Container with templates for export | releases 4.7.2-stable 2026-08-18 | workflow `container: barichello/godot-ci` | ❌ refuse as default (Linux-only, version lives in an image tag away from the csproj); fine for exports |
| Tests (C#) | GdUnit4Net (gdUnit4.api + test adapter, `dotnet test`) | Runs in `dotnet test`, scene runner, plugin for editor | MikeSchulze/gdUnit4Net: pushed 2026-10-06 but latest GitHub release v5.0.0 is 2025-06-21 (release lag?); gdUnit4 GDScript 6.2.2 2026-10-07; gdUnit4-action 1.3.2 2026-06-28 | Packages contain `gdUnit4`; test project; a recipe running it | untested for 4.7.2/net10/MTP |
| Tests (C#, alt) | Chickensoft GoDotTest | Runs tests inside the engine via `--run-tests --quit-on-finish`; coverage with coverlet | chickensoft-games/GoDotTest 2.0.47, 2026-09-09 | `GoDotTest` package + `--run-tests` in Makefile | untested (best CLI/headless story; needs a test-scene switch in Main) |
| Tests (GDScript) | GUT 9.6.1 | Only if GDScript is used | bitwes/Gut, 2026-07-09 | `.gd` present and `gut` in Makefile | `na` for lifesim |
| Scene/resource integrity | Godot's own import (`--headless --import` prints errors for broken refs) | No maintained static `.tscn` linter found in this pass | none found | grep import log for `ERROR`/`Parse Error` (never seen red) | untested; do not claim a tool |
| UID files | Commit `*.uid` (Godot 4.4+), never ignore them | UIDs keep references valid across renames | Godot 4.4 release notes; lifesim commits `Main.cs.uid` (not re-verified in docs this pass) | `.gitignore` must not match `*.uid`; every `*.cs`/`*.gd` in the Godot folder has a sibling `.uid` (`git ls-files`) | ✅ adopt as a check; evidence one pass |
| VCS hygiene | `.godot/` ignored; `.gitattributes` with `* text=auto eol=lf`; LFS for binaries | Godot docs: generated by Project > Version Control | godot-docs `version_control_systems.rst` ("Files to exclude from VCS", `.godot/`, `*.translation`) | `.gitignore` contains `.godot/`; `.gitattributes` exists with `eol=lf` | ✅ adopt; lifesim lacks `.gitattributes` |
| `*.import` files | Commit them | Per-asset import settings | godot-docs, one pass | `.import` present beside assets, not ignored | ✅ adopt (lifesim has no assets yet) |
| export_presets.cfg | Commit it; credentials go in `.godot/export_credentials.cfg` (ignored) in Godot 4.1+ | Docs warn 3.x/4.0 differ and may store credentials in the file | godot-docs same page | file present with no secrets; `.godot/` ignored | ✅ adopt when exporting; lifesim has none |
| project.godot settings | `config/features` includes version and "C#"; `[dotnet] project/assembly_name` equals csproj name; rendering method explicit | assembly_name mismatch breaks the C# load | lifesim project.godot | `assembly_name` equals csproj `AssemblyName`/file stem | ✅ adopt |
| Architecture | MSBuild `ForbidGodotInSim` + BannedApiAnalyzers + ArchUnitNET | Sim stays testable without the engine | lifesim Directory.Build.props | `Directory.Build.props` contains `GodotSharp` inside a Sim-scoped Target; `dotnet build` | ✅ adopt (already) |
| Chickensoft patterns | LogicBlocks, AutoInject, GodotNodeInterfaces | Typed nodes, testable views | chickensoft-games org, not evaluated here | none | untested; do not mandate |

## Open items for the engine
- `root` concept: lifesim's Godot project is `src/Game.Godot`; profile paths must resolve under repo root and under each folder containing `project.godot`.
- Globs: CI workflow file names and `*.csproj` are not fixed; `config.path` needs glob support.
- A `.uid` sibling check and an `ENGINE-VERSION` equality check (csproj Sdk vs `config/features` vs CI) are scripted checks, not substring checks: need a custom concern.
- Never-seen-red rule: scene-integrity log scan and the tests role stay untested until proven.
