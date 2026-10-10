# .NET stack profile + Godot framework profile layered on it

Date 2026-10-10. Method: ONE pass. Release dates from the GitHub/NuGet APIs (`gh api`, api.nuget.org), docs fetched once, and
experiments on a scratch copy of lifesim (Godot 4.7.2 mono, dotnet SDK 10.0.301, prek 0.5.5; lifesim itself untouched).
T = run in the experiments, D = read in docs, J = judgement, no source. Outputs: `profiles/dotnet.toml`, `profiles/frameworks/godot.toml`.
Principle: everything best for .NET, Godot adds on top, the two must hold together.

## 1. Stack roles (.NET 10, C# 14)

| Role | Tool | Why | Evidence (release date) | Signal | Verdict |
|---|---|---|---|---|---|
| toolchain | global.json (`rollForward latestPatch`) + NuGet lock files, locked mode in CI | pin = reproducible; lifesim's `latestFeature` lets the SDK drift | dotnet/sdk v10.0.401 2026-09-08 (github.com/dotnet/sdk); lock + Godot SDK restore T | global.json `version`, `rollForward`; props `RestorePackagesWithLockFile` | ✅ |
| formatter | CSharpier 1.3.0 local tool | one layout owner, no config | github.com/belav/csharpier 2026-06-07; T: `csharpier check` on Game.Godot passes | `.config/dotnet-tools.json`; `csharpier check` in gate | ✅ |
| linter | SDK analyzers `latest-all` + Meziantou 3.0.297 (2026-10-10) + Roslynator.Analyzers 5.0.1 (2026-10-04) + SonarAnalyzer.CSharp 10.35 (2026-09-28); severities in .editorconfig | overlapping coverage, all current | github.com/meziantou/Meziantou.Analyzer, dotnet/roslynator, SonarSource/sonar-dotnet | props has TreatWarningsAsErrors, latest-all, EnforceCodeStyleInBuild, the 3 packs | ✅ |
| linter, refused | StyleCopAnalyzers 1.1.118 (2019-04-29) | dead stable line; layout rules fight CSharpier | github.com/DotNetAnalyzers/StyleCopAnalyzers | - | ❌ |
| linter, refused | Roslynator.Formatting.Analyzers | second layout owner next to CSharpier | J | - | ❌ |
| types | `Nullable enable` + `WarningsAsErrors nullable` | strictest, built in | lifesim props T | props `Nullable` | ✅ |
| dependencies | CPM + `CentralPackageTransitivePinningEnabled` + NuGetAudit (`all`, `low`); NU1901-4 become errors via TreatWarningsAsErrors; `WarningsNotAsErrors NU1900` for offline | vulnerable or drifting package fails build; no deptry equivalent for unused packages (gap) | learn.microsoft.com/nuget/concepts/auditing-packages (D, not re-fetched); restore+build with audit T | props: MPVC, pinning, NuGetAuditMode | ✅ (unused-package check: none found) |
| tests | xunit.v3 4.0.2 (2026-10-09) on Microsoft.Testing.Platform; global.json `test.runner` | native MTP; ArchUnitNET.xUnitV3 and CsCheck fit | github.com/xunit/xunit; lifesim runs it | global.json MTP; `dotnet test` in gate | ✅ |
| tests, alt | MSTest 4.5.1 (2026-10-07), TUnit 1.73.19 (2026-10-08) | both MTP-native | github.com/microsoft/testfx, thomhurst/TUnit | - | untested (no reason to leave xunit) |
| coverage | candidates coverlet.MTP 10.1.0 (2026-09-27) `--coverlet-threshold`; Microsoft.Testing.Extensions.CodeCoverage 18.12.0 | floor needs a failing exit | learn.microsoft.com/dotnet/core/testing/microsoft-testing-platform-code-coverage (updated 2026-10-01): MTP exit code 14 on failed threshold; coverlet page lists the option AND says "Threshold validation is not yet supported" | `--coverlet-threshold` in gate | untested: never run red/green; contradictory docs |
| spelling | typos 1.51.1 (2026-10-06) | identifier splitting, one binary, hook-friendly | github.com/crate-ci/typos | typos config + `typos` in gate | ✅ chosen, not run on C# here (binary not installed) |
| spelling, alt | codespell | the python profile's tool | - | - | ❌ (needs python in a .NET repo) |
| architecture | BannedApiAnalyzers 5.6.0 + `BannedSymbols.*.txt`; ArchUnitNET 0.13.4 (xUnitV3 pkg) | banned APIs at compile time; layer/module tests | NuGet; lifesim uses both | props + `BannedSymbols*.txt`; gate build | ✅ |
| architecture, refused | NetArchTest 1.3.2 (2021-05-23) | abandoned | github.com/BenMorris/NetArchTest | - | ❌ |
| hooks | prek: `dotnet csharpier check` (types `c#`) + typos per commit; `make check` on pre-push | fast on staged files; build is too slow per commit | T: csharpier hook green 0.5 s on 5 files, prek 0.5.5 | `.pre-commit-config.yaml` contains both | ✅ |
| agent-guidance | `docs/agents/dotnet.md` + link in AGENTS.md | see section 4 | J | file + link | ✅ |

## 2. Compatibility matrix .NET x Godot (Godot.NET.Sdk 4.7.2, net10.0)

| .NET choice | Status in the Godot csproj | Resolution |
|---|---|---|
| Directory.Build.props inheritance | works T: strict props apply, `dotnet build src/Game.Godot -warnaserror` 0 warnings | keep `Sdk="Godot.NET.Sdk/x.y.z"` and `TargetFramework` written in the csproj (lifesim's comment: the editor rewrites a csproj missing them; not re-verified) |
| TreatWarningsAsErrors + Godot generators | works T: `[GlobalClass]`, `[Signal]`, `[Export]` partial class produced no warning | none; GD0001 (missing `partial`) stays an error (docs.godotengine.org .../diagnostics/GD0001, D) |
| Nullable in Godot scripts | works T: `PackedScene? Target` exported property compiled clean | `[Export]` non-nullable fields need `= null!`/defaults; not tested |
| Analyzers on scene callbacks | CONFLICT T: CA1822 and S2325 fail a scene-wired `OnBodyEntered` | `dotnet_diagnostic.CA1822/S2325.severity = none` in the Godot folder scope, beside lifesim's CA1707, IDE1006, CA1812, CA1515 |
| Central package management | works T: Godot.NET.Sdk's implicit GodotSharp 4.7.2 refs coexist with CPM | none |
| Lock files + audit + transitive pinning | works T: restore, `--locked-mode`, build all green with `Game.Godot` | lock files regenerate on engine bump; commit them |
| CSharpier on Godot scripts | works T | `.csharpierignore` has `.godot/`, `obj/`, `bin/` (lifesim has them) |
| xunit.v3 / MTP tests | no engine needed: only Sim projects tested; `Game.Godot` references GodotSharp native bits and cannot run outside the engine | keep logic in engine-free projects; views get in-engine tests only |
| GdUnit4Net 5.0.0 (VSTest adapter) | probably conflicts with an MTP-only `dotnet test` (global.json runner MTP); D: README mentions VSTest only, runs without the engine unless `[RequireGodotRuntime]`; repo moved to godot-gdunit-labs, 27 open issues; 5.1.0-rc5 on NuGet, stable 2025-06-21 | not chosen; untested |
| GoDotTest 2.0.47 | no clash: own runner inside the engine (`--run-tests --quit-on-finish`), needs a test switch in the main scene (D) | candidate; untested here |
| Coverage in Godot | engine-free projects: normal tools. In-engine: only coverlet launching Godot via GoDotTest (D) | floor applies to Sim projects; view code excluded |
| BannedApiAnalyzers / Forbid target | works T (lifesim); the Godot csproj must not carry the core marker | keep `IsSimProject` false there |
| `make check` vs engine | `godot --headless --import` and `--build-solutions` need the engine binary: a machine without it cannot pass `check` | `GODOT` var; CI installs it; accept (gate stays one command) |

## 3. Godot roles

| Role | Tool | Evidence | Signal | Verdict |
|---|---|---|---|---|
| engine-version | `Godot.NET.Sdk/x.y.z` exact in the csproj; `config/features` match; CI derives the version from it | godotengine/godot 4.7.2-stable 2026-08-18; setup-godot can read `global.json` msbuild-sdks (github.com/chickensoft-games/setup-godot, v2.4.3 2026-10-01) but that drops the version from the csproj, which lifesim says the editor rewrites | csproj regex, project.godot `4.` | ✅ csproj as source |
| project-hygiene | `.godot/` ignored; `*.uid`, `*.import` committed; `.gitattributes` `text=auto eol=lf`; clean tree after import | docs.godotengine.org/en/stable/tutorials/best_practices/version_control_systems.html: excludes `.godot/`, `*.translation`; silent on `.uid`. T: headless import regenerates a deleted `Main.cs.uid` | `.gitignore`, `.gitattributes`; porcelain empty after import | ✅ |
| assets | Git LFS patterns in `.gitattributes`; export_presets committed | same page (D); lifesim has no assets | `filter=lfs` | ✅; OPEN: LFS pre-push upload under prek (git-lfs wants its own pre-push hook and stdin refs) never tried |
| scripts-lint | `na` while C#-only. Later: gdtoolkit 4.5.0 (2025-10-09, stale) or GDQuest GDScript-formatter 0.27.0 (2026-09-25) | github.com/Scony/godot-gdscript-toolkit, GDQuest/GDScript-formatter | `.gd` appears | na |
| build | `--headless --path <root> --import` then `--build-solutions --quit` inside `check` | docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html (D); T: compile error gives exit 1 | Makefile has `--build-solutions` reachable from check | ✅ (lifesim keeps it outside check: gap) |
| tests | GoDotTest vs GdUnit4Net | see matrix; GoDotTest 2.0.47 2026-09-09; gdUnit4Net 5.0.0 2025-06-21, pushed 2026-10-06 | - | untested |
| scene-integrity | scan the import log for `ERROR:` | T: import and run exit 0 even with a broken `ext_resource` (errors only in the log); clean import gives 0 `ERROR` lines; broken script path and bad scene line each gave `ERROR:` | `ERROR:` in the recipe | ✅ seen red and green for two failure kinds; missing texture/sub-resource not tried |
| architecture | ForbidEngineInCore target + BannedApi + thin Godot csproj + CA1822/S2325 off in the Godot scope | lifesim props; T for the analyzer finding | `GodotSharp` in props, `CA1822` in .editorconfig | ✅ |
| ci | actions/setup-dotnet + setup-godot@v2 + `make check`; abarichello/godot-ci image only for exports | setup-godot: macOS, Windows, Ubuntu runners (D) | workflow has `setup-godot`, `make check` | ✅ |
| hooks | prek local hook `godot-uid` (sibling `.uid` for staged `.cs/.gd` in the Godot folder) | T: green on lifesim, red on a new `Bad.cs` | contains `godot-uid` | ✅ |
| agent-guidance | `docs/agents/godot.md` | section 4 | file + link | ✅ |

## 4. Agent-guidance recommendation (J, no external source)

Layout: `AGENTS.md` (map, 60 lines) -> `docs/agents/dotnet.md`, `docs/agents/godot.md` -> a 10-20 line `AGENTS.md` per top-level code folder (lifesim already does this for `src/`, `tests/`).
- dotnet.md: commands (`make check|build|test|fmt`); props files are the only home for settings and versions; analyzers are fixed by .editorconfig lines with a reason, never `#pragma`/`SuppressMessage`; no `!` outside tests; layering table; test naming.
- Comments: `// why:` for decisions an agent cannot infer (units, determinism, workaround + link); XML `<summary>` on public types and entry points of library projects stating contract and invariants, not on every member (lifesim silences CS1591: acceptable, better is CS1591 as error in Sim libs only); no file headers; no comment restating code.
- godot.md: engine pin; headless commands; `partial` is mandatory; `[Signal]` delegates end in `EventHandler`; scene-wired callbacks stay instance methods; never hand-edit `.godot/` or `*.uid`; views read snapshots and send commands; after editing a `.tscn` run the build target and read the `ERROR:` lines.
- Keep each file under 150 lines; link, do not paste, evolving facts.

## 5. lifesim vs the profile

| Gap | Role |
|---|---|
| no lock files, `rollForward latestFeature`, no NuGetAudit settings, no transitive pinning | toolchain, dependencies |
| no coverage; no typos config | coverage (profile itself untested), spelling |
| no `.pre-commit-config.yaml` (bd hooks run from `.beads/hooks`), no csharpier/typos/godot-uid hooks | hooks (stack + framework) |
| no `docs/agents/dotnet.md`, `godot.md` (rules live in `design/runbooks/code-structure.md`) | agent-guidance |
| `.editorconfig` Godot scope lacks CA1822, S2325 (would fail at the first signal handler) | architecture |
| `godot-import` outside `check`; no import-log scan; no clean-tree check | build, scene-integrity |
| no `.gitattributes`, no LFS | project-hygiene, assets |
| no CI | ci |
| `prototype/mac-render-spike` has its own project.godot: engine reports it as a second Godot project | open: blueprint.toml `[profile.frameworks]` |
| global.json does not pin Godot (csproj does; fine by this profile) | engine-version |

## Re-judged under the age rule (2026-10-10)

Owner rule: age alone never disqualifies a tool; refuse only when abandoned (archived, broken on the current toolchain, users moved to a successor). Tools whose refusal or demotion leaned on age were re-checked the same day: NuGet/PyPI totals, GitHub API (archived, stars, last commit, issues), and scratch builds under .NET SDK 10.0.301 / net10.0 / LangVersion 14 (T) or gdtoolkit 4.5.0 in a fresh venv (T). Searched `dotnet-godot-layering.md`, `godot-profile.md`, `lifesim-strategy.md`; no other tool was refused on age. DefaultEcs is not mentioned anywhere; Arch lost the ECS spike on missing shapes (links, relations, indexes), not age, so it is out of scope. Verify was refused for its sponsorship check, not age.

| Tool | Use evidence | Compatibility | Old verdict | New verdict | Reason |
|---|---|---|---|---|---|
| StyleCop.Analyzers (stable 1.1.118, 2019; beta 1.2.0-beta.556, 2023-12; successor package StyleCop.Analyzers.Unstable 1.2.0.556) | NuGet 276.6M total (Unstable 125.7M); GitHub DotNetAnalyzers/StyleCopAnalyzers 2.9k stars, not archived, commits on 2026-10-10 (C# 15 tests on .NET 11 reference assemblies), 257 open issues | T: Unstable 1.2.0.556 on net10.0 / C# 14 (collection expressions, tuples, records) builds, no crash, no analyzer exception | ❌ "dead stable line; layout rules fight CSharpier" | ❌ refuse, reason changes: conflict, not age | T on CSharpier 1.3.0 output: SA1513 fires on formatted code (layout owner clash), plus SA1101 (`this.`), SA1309 (no `_field`), SA1633 (file header), SA1402, SA1204 contradict the profile's own conventions (no file headers; lifesim naming). Turning off those leaves only ordering/doc rules that Meziantou + Roslynator + Sonar + SDK `latest-all` already cover. Not abandoned; just redundant and in conflict. If a repo wants the SA12xx ordering rules, add `StyleCop.Analyzers.Unstable` (never the 2019 stable id) with SA1101/1309/1633/1402/1513 and all layout/spacing ids at `none` |
| Roslynator.Formatting.Analyzers | 5.0.1 released 2026-10-04, current | works (same release train as Roslynator.Analyzers) | ❌ second layout owner | ❌ unchanged | conflict with CSharpier, not age (it was never refused on age) |
| NetArchTest.Rules 1.3.2 (2021-05-23) | NuGet 16.8M total; GitHub BenMorris/NetArchTest 1.8k stars, not archived, last commit 2023-07-03, last push 2024-07, 25 open issues (one open since 2025-05: immutability check misses C# 9 `init`) | T: net10.0 console, LangVersion 14: `ShouldNot().HaveDependencyOn` correct in both directions, caught dependencies via a primary constructor, a lambda body and a generic argument | ❌ "abandoned" | ❌ refuse, reason changes: duplicate of a live tool in the same role, not abandoned | Works, widely used, not archived, so age does not refuse it. Refused because ArchUnitNET already owns the role: TngTech/ArchUnitNET 1.4k stars, pushed 2026-10-10, 0.13.4 released 2026-08-20, 9.4M downloads, in lifesim, with an xUnit v3 package. Two architecture-test libraries means two rule vocabularies. Successor split: fork NetArchTest.eNhancedEdition 1.4.5 (2025-06, 1.0M downloads, 53 stars; different API, `HaveDependencyOn` is not on its Condition type; not adopted). Adopt NetArchTest.Rules only for a repo that already has it |
| gdtoolkit (gdlint, gdformat) 4.5.0 (2025-10-09) | PyPI ~1.05M downloads (non-mirror, last 180 days), ~235k last month; GitHub Scony/godot-gdscript-toolkit 1.6k stars, not archived, 52 open issues, no commit since 2025-10-09 and no maintainer reply on recent issues (issues from users keep arriving through 2026-10) | T: gdlint 4.5.0 + gdformat 4.5.0 install on python 3.x; parse a file with typed `Dictionary[String, int]`, `Array[String]`, lambdas, `match`, `await`, `@export_group`, `@warning_ignore`, `%Node`, `static func`, and Godot 4.5 `@abstract`; lint catches bad class/function names (exit 1), `gdformat --check` flags unformatted code (exit 1). Syntax added in 4.6/4.7 not exercised. Open formatter bugs: output after a multiline lambda can be rejected by Godot (issue 2026-07-03), `gdlint` rejects `@abstract func ...;` with a semicolon | "stale", scripts-lint `na`, candidates untested | ✅ adopt as the scripts-lint tool once a `.gd` file exists: `gdlint` + `gdformat --check` (check only; never auto-format in a hook). GDQuest GDScript-formatter 0.27.0 (2026-10-08 commit, 470 stars) stays the untested formatter alt | Stale maintainer is not abandonment: not archived, no successor for the linter (the GDQuest tool is a formatter only), a million-plus downloads, works on the syntax tested. Risk logged: single silent maintainer; the `na` row in godot.toml is reworded, not made mandatory, because a C#-only repo has no `.gd` |
| GdUnit4Net 5.0.0 (stable 2025-06-21; 5.1.0-rc5 on NuGet) | not refused on age; repo godot-gdunit-labs/gdUnit4Net 189 stars, pushed 2026-10-06 | not tested here | untested (VSTest vs MTP) | untested, unchanged | listed because the stable-release date looked old; the open question is the MTP clash, not age |

Net effect: no verdict flips from ❌ to ✅ for a .NET role. One flips for Godot: scripts-lint now names gdtoolkit instead of "stale". Two refusals stand with the age reasoning removed (StyleCop: conflict; NetArchTest: duplicate).
