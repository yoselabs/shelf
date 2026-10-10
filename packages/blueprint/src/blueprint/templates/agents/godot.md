# Godot conventions

Framework layer on top of [dotnet.md](dotnet.md) for a Godot 4.x C# game: every .NET rule applies to the
Godot project too. `{{godot_root}}` is the folder holding `project.godot`.

## Tools per role

| role | tool | enforced by |
|---|---|---|
| engine-version | `Godot.NET.Sdk/<x.y.z>` exact in the Godot `.csproj` (single source); `config/features` in `project.godot` has the same major.minor | config check |
| project-hygiene | `.godot/` ignored; `*.uid` and `*.import` committed; `.gitattributes` with `text=auto eol=lf` | config check, clean tree after import |
| assets | Git LFS patterns in `.gitattributes` for binaries; `export_presets.cfg` committed, credentials only in `.godot/export_credentials.cfg` | config check |
| build | `godot --headless --path {{godot_root}} --import`, then `--build-solutions --quit`, both inside `make check` | gate |
| scene-integrity | the import log is scanned: any `ERROR:` line fails the gate | gate |
| architecture | the engine-free core cannot reference `GodotSharp`; the Godot project references the composition root only | MSBuild target, BannedApiAnalyzers |
| hooks | prek `godot-uid`: every staged `.cs`/`.gd` has a sibling `.uid` | hook |
| tests | engine-free logic in xunit projects; in-engine tests only for thin views (runner not chosen) | untested |
| scripts-lint | not applicable while C#-only; with the first `.gd` file add gdtoolkit (`gdlint`, `gdformat --check`) | - |
| ci | none for now: agents run `make check` on a machine with the Godot .NET binary (`GODOT` env var) | - |

## Run

```bash
make check         # includes godot-build: import, scan for ERROR:, build solutions, clean-tree check
make godot-build   # after editing any .tscn, .tres or script: read the ERROR: lines
```

Without the matching Godot .NET binary the gate cannot pass: set `GODOT` to it.

## Rules

| rule | why |
|---|---|
| Never hand-edit `.godot/` or `*.uid` | The engine regenerates them; hand edits are overwritten |
| A new script means commit its `.uid` (open the project in the editor or run the headless import) | A missing `.uid` breaks references on other machines |
| Node scripts are `partial` classes (missing `partial` is error GD0001) | The source generator needs it |
| Signals are `[Signal] public delegate void NameEventHandler(...)` | The generator derives the signal from the delegate name |
| Views read snapshots from the core and send commands; no game rules in nodes | Rules stay testable without the engine |
| A scene-wired callback stays an instance method | See traps |
| The Godot project must not carry the core marker property | Else the engine-free check would forbid its own references |
| Comment `// why:` for engine quirks with a link; do not narrate the scene tree | The `.tscn` is the source of truth for structure |

## Layout

| thing | where |
|---|---|
| Composition root | one project the Godot project references; the only wiring point |
| Scenes and scripts | `{{godot_root}}/`, a script beside its scene, named alike (`Player.tscn`, `Player.cs`) |
| Engine-free logic | its own projects with their own tests, never under `{{godot_root}}` |

## Traps

- Scene-wired handlers (`OnBodyEntered`) look static to CA1822 and S2325; making them static breaks the scene wiring. The Godot folder's `.editorconfig` scope sets those two (and CA1707, IDE1006, CA1812, CA1515) to `none`. Do not "fix" the warning in code.
- The headless import exits 0 on a broken scene reference; only the log shows it. Never skip the `ERROR:` scan.
- After a headless import `git status --porcelain` must be empty; a new `.uid` or `.import` file means something was not committed.
- The editor rewrites a `.csproj` missing the `Sdk="Godot.NET.Sdk/x.y.z"` version or an explicit `TargetFramework`; keep both written.
- `[Export]` non-nullable fields need a default (`= null!` or a value) under strict nullability.
- A second `project.godot` in the repo (a spike folder) is reported as a second project; keep spikes out or declare them.
