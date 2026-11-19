# Unity framework profile (draft) layered on the .NET stack profile

Date 2026-10-11. Adopted as `packages/blueprint/src/blueprint/profiles/frameworks/unity.toml`, `templates/agents/unity.md` and the `unity-integrity` recipe (`recipes/unity_integrity.py`).
Labels: **T** = run here on Unity **6000.7.0b4** (6.7 BETA; the only editor on this Mac, /Applications/Unity/Hub/Editor), macOS arm64, .NET SDK 10.0.401, scratch project under the session scratchpad (`lab/g1`); **R** = read (URL, 2026-10-11); **J** = judgement; **U** = untested.
Every T result is for 6000.7.0b4, NOT for the 6000.3 LTS the profile recommends. No consumer repo exists; no repo was modified; nothing committed. No file was downloaded: analyzers came from the local NuGet cache (~/.nuget/packages), so Microsoft.Unity.Analyzers (not cached) is U.

## 1. Which release line

| Line | Status on 2026-10-11 | Evidence |
|---|---|---|
| 6000.0 LTS | support ends Oct 2026 | R unity.com/releases/unity-6/support |
| 6000.3 LTS | latest LTS, support to Dec 2027 | R same page |
| 6.4 (2026-03-19), 6.5 (Aug 2026), 6.6 (Sep 2026) | "Update"/supported releases, fixes only until the next release | R strayspark.studio roadmap post; unity forum titles via search |
| 6000.7 | BETA (6000.7.0b4 installed here); planned as the next LTS, expected Q4 2026, last Mono-based release; experimental CoreCLR player; CoreCLR editor targeted for 6.8 | R unity.com discussions "CoreCLR, Scripting, and ECS Status Update - March 2026" (via search summary), docs.unity.com/en-us/engine/6000.7/manual |

Verdict: **pin the newest LTS stream: 6000.3.x today, move to 6000.7 LTS when it ships.** Refused: 6000.0 LTS (support ending = abandonment), 6.4-6.6 for a product repo (support ends at the next release), 6000.7 beta for anything but this research (a beta is not a pin). Open for the owner: a game starting now could choose 6.7 LTS at release; the profile's checks accept any `m_EditorVersion: 6000.` so the choice does not need a profile change.
Caveat that matters: the LTS I could not run (6000.3) may differ from the 6000.7.0b4 results below in Roslyn version (6000.7 bundles .NET SDK 10.0.303, Roslyn 5.0; 6000.3 bundles an older Roslyn, U), package versions (Test Framework 1.9.0 builtin here), and the generated project format (6000.7 writes `.slnx`). Re-run the lab on 6000.3 before promoting the status.

## 2. Detection

| Item | Rule |
|---|---|
| Marker | `ProjectSettings/ProjectVersion.txt` (always present, text, written by every editor). `Packages/manifest.json` is a second confirmation, not a marker: non-Unity repos can have a `Packages/` folder. |
| Framework root | the marker's **grandparent** (the folder holding `ProjectSettings/`). |
| profile.py change | `FRAMEWORK_MARKERS = {"godot": "project.godot"}` plus `walk(repo, marker, 4, skip)` returns `p.parent`. For `unity` the marker is a path with a folder; `walk` matches file names (J, not read in detail), and the root needs `p.parent.parent`. REQUIRED code change: e.g. `FRAMEWORK_MARKERS["unity"] = ("ProjectVersion.txt", "ProjectSettings")` with a parent check, or a `root_up` count. The toml cannot express it. |
| Skips | `Library/PackageCache/**` and `Packages/*` embedded packages never contain a Unity project; the existing SKIP_DIRS must include `Library` (J) or a copied sample project inside a cached package could be detected. |
| .NET detection | `_stack_files` finds `dotnet` from `*.sln/*.slnx/*.csproj`. A clean clone has none (Unity's are generated and ignored), so the dotnet rows would not be judged. The committed hand-written `tests/<Name>.Core.Tests/*.csproj` (needed anyway for engine-free tests) makes `dotnet` detect. State this in unity.md's install text, done. Anchor the ignore patterns (`/*.csproj`), or the tests csproj is ignored. |

## 3. Per-role verdicts

| Role | Tool / answer | Verdict | Evidence |
|---|---|---|---|
| framework-version | ProjectVersion.txt pin; policy = newest LTS; packages-lock.json committed; build target compares `Unity -version` | ✅ | T: createProject wrote ProjectVersion.txt (`m_EditorVersion: 6000.7.0b4`, `m_EditorVersionWithRevision: 6000.7.0b4 (9debfb8362db)`) and `Packages/packages-lock.json` (registry packages locked with url, builtin as `source: builtin`). R: GameCI reads the same file. U: the `-version` comparison and the Hub CLI install |
| project-hygiene | anchored .gitignore; Force Text + Visible Meta Files; .meta pairing; GUID uniqueness; LF | ✅ | T: 6000.7 defaults are Force Text (`m_SerializationMode: 2`) and Visible Meta Files. T: my `unity_integrity.py` red on 6 planted faults (missing .meta, orphan .meta, duplicate GUID, bad meta, Force Text off, Hidden Meta Files), green on the clean project. T: Unity regenerates a missing .meta (new GUID when Library is cold, same when warm: `Counter.cs.meta` guid 3553... became 8c12... after `rm -rf Library`), deletes an orphan .meta on import, writes .meta for new files; each leaves `git status --porcelain` dirty. Note: createProject writes NO .gitignore and NO .gitattributes |
| project-hygiene, smart merge | UnityYAMLMerge (`Contents/Helpers/UnityYAMLMerge`, rules in `Resources/UnityYAMLMerge/`) as git merge driver | **U, with a warning** | T: the driver `merge -p %O %B %A %A` blocked a `git merge` by launching Apple FileMerge (the fallback tool list in mergespecfile.txt), killed after 120 s; run by hand it exited 0 and wrote a 0-byte result. My scene was hand-written, so this may be my fault, but an agent must not install the driver until it is proven on a real scene. Not in the profile |
| binary-assets | Git LFS via .gitattributes | ✅ (config only) | J + R; git-lfs 3.x present on the Mac; T: none (no assets). Open: LFS under prek pre-push (same as Godot). Size budget U |
| embedded-script-lint | shaders: none | U | T negative: a shader with an undefined HLSL symbol imported with exit 0 and no log line; `ShaderUtil.ShaderHasError` false under `-nographics`. No HLSL linter evaluated. Not proposing one by name |
| build | `Unity -batchmode -nographics -quit -projectPath` in `make check`, clean-tree check; player build as a separate target | ✅ | T: exit 0 clean, exit 1 on `error CS0029` (planted), log has `Assets/...cs(1,74): error CS...`. T: cold Library 95 s on an empty project. T: `BuildPipeline.BuildPlayer` macOS Mono standalone in 2 min 21 s, Result: Success, exit 0 via `EditorApplication.Exit`. Licensing: the log prints a licensing handshake error and still reports "Unity Personal"; works. U: Windows/Linux runners, Hub CLI install, IL2CPP |
| tests | UTF `-runTests` + results XML; pure core via dotnet | ✅ | T EditMode: pass exit 0 + XML; planted failing assert exit 2; compile error exit 1 and NO XML. T PlayMode headless with `-nographics`: passed (1 UnityTest covering `async Awaitable Start` and fake null). T: xunit.v3 (4.0.2, MTP) project linking `Assets/Scripts/Core/**/*.cs` with `LangVersion 9.0` green, needs `global.json` with the MTP runner and `dotnet test --project`. R: net10.0 ≠ netstandard2.1 API surface; a netstandard2.1 library csproj linked to Core and referenced by the test project would test the Unity surface (J, advisor idea, U) |
| surface-integrity | `CiValidate` editor script + integrity script | ✅ partial | T: scene with a MonoBehaviour GUID `deadbeef...` -> `MISSING-SCRIPT Assets/Scenes/Main.unity: 1`, exit 3. Gaps by test: shaders (above); broken asset/texture references (U); Addressables (U). A text scan for `m_Script` GUIDs was NOT adopted: references into registry packages (TMP, UGUI) cannot be resolved on a clean clone without Library/PackageCache (J) |
| architecture, layer map | `.asmdef` references + `noEngineReferences` | ✅ | T: `Game.Core` (noEngineReferences) compiled; the Runtime asmdef referencing Core compiled. R: docs. U: a planted `using UnityEngine;` in Core was NOT run (I expect CS0234; unverified), nor a missing-reference edge |
| architecture, banned APIs | Microsoft.CodeAnalysis.BannedApiAnalyzers | **❌ in the editor, ✅ in dotnet** | T: BannedApi DLL labelled `RoslynAnalyzer` loads, but its `BannedSymbols.txt` can only reach Unity's compile as `*.<Analyzer>.additionalfile` (R docs.unity.com 6000.7 .../roslyn-analyzers/additional-files); `/additionalfile:` in an `.rsp` is dropped (T). The analyzer matches files named `BannedSymbols*.txt` (J, from its source behaviour), so `DateTime.Now` was NOT flagged (T). Works under `dotnet build` (dotnet profile, T previously) |
| architecture, namespace rules | NsDepCop 3.2.0 | **❌ in the editor, ✅ in dotnet (config discovery caveat)** | T: in the editor the DLL first fails reference validation; after labelling it loads and reports nothing for a planted `using System.Text` under a default-deny config passed as `config.NsDepCop.Analyzer.additionalfile`. T: in `dotnet build` of the generated csprojs it reports NSDEPCOP03 "No config file found" for each, because it reads `$(ProjectDir)config.nsdepcop` and all generated csprojs sit in one folder: the same one-config-for-all trap the Godot research refused. Namespace rules inside Unity assemblies: U (needs per-asmdef config files in a `Game.<Layer>/` project dir; not tried). asmdef references carry the layer DAG |
| architecture, ArchUnitNET | on the Core test project | U | not run on Unity code |
| linter, strict .NET set on Unity code | via `dotnet build <name>.slnx` of the regenerated solution | ✅ | T: `rm *.csproj *.slnx` then a plain `Unity -batchmode -quit` regenerates them (Game.*.csproj + g1.slnx); `dotnet build` builds them (netstandard2.1, LangVersion 9.0, 6 s for Core); Meziantou + Roslynator + Sonar + Threading + IDisposable + ErrorProne + SharpSource + Nullable.Extended + Reflection analyzers ran on `Game.Runtime`; the project-name condition kept package csprojs clean; `-warnaserror` failed the build with 20 errors on the lab code. R: Microsoft.Unity.Analyzers 1.28.0 (2026-09-29, 816 stars, not archived) U |
| linter, in-editor analyzers | `RoslynAnalyzer`-labelled DLLs | ⚠ optional | T: label via `AssetDatabase.SetLabels` + `PluginImporter` (Any/Editor off) sets `validateReferences: 1`; **an analyzer DLL at `Assets/` root also runs on package assemblies** (PackageCache `UnityEngine.TestRunner` produced MA0037/MA0049 errors and the build failed, exit 1); inside an asmdef folder it governs that assembly (T). **`.editorconfig` is ignored by Unity's compile** (T: `dotnet_diagnostic.MA0006.severity = error` left a warning, exit 0); `-analyzerconfig:` in `<Asm>.rsp` pointing at an `is_global = true` file works (T: error, exit 1). Chicken-and-egg: once a rule is `error`, scripts do not compile, so a labelling `-executeMethod` cannot run; commit the labelled .meta. Binary DLLs in Assets add supply-chain and LFS questions; the dotnet-build gate covers the same rules, so in-editor analyzers are optional (J) |
| linter, rsp forwarding | | T | `Assets/csc.rsp`: `-nullable:enable` and `-warnaserror+` are forwarded (Library/Bee/.../Game.Core.rsp shows both; CS8602 became an error; package assemblies untouched). Per-asmdef `<Asm>.rsp`: only `-analyzerconfig` forwarded; `-nullable`, `-warnaserror+`, `-additionalfile` dropped |
| formatter | CSharpier 1.3.0 (the dotnet profile's), `.csharpierignore` for Library/Temp/Logs/UserSettings/Builds/obj | ✅ | T: `dotnet csharpier check Assets` listed my unformatted one-liner file as a diff (non-zero), clean file passes. dotnet format / Roslynator.Formatting stay refused (dotnet profile) |
| dependencies | Unity Package Manager manifest + packages-lock.json for Unity packages; NuGet CPM for the dotnet side only | ✅ J | T: packages-lock.json exists. U: CPM with the generated csprojs (injected PackageReferences carry no Version => NU1008; Directory.Packages.props must list the analyzers by id), and `RestorePackagesWithLockFile` collides across N csprojs in one folder (needs `NuGetLockFilePath=$(MSBuildProjectName).packages.lock.json`; U) |
| ci | GameCI | **U (TBD)** | R: game-ci/unity-test-runner v4.4.0 (2026-09-09), unity-builder v5.0.1/v4.8.2 (2026-09-01), repos not archived (gh api 2026-10-11). R game.ci/docs/github/activation: Personal needs a `.ulf` in a secret + email/password, Pro a serial, or a license server. Not exercised; owner decision on whether Unity gets CI |
| hooks | prek `unity-integrity` + csharpier | ✅ (script), U (prek run) | T: script red/green; prek not run on it. Never start the editor in a hook |
| agent-guidance | docs/agents/unity.md | ✅ | draft unity.md; T for fake null (`go == null` true after DestroyImmediate, `go is null` false), `async Awaitable Start` |

## 4. .NET x Unity compatibility

| .NET profile choice | In Unity code | Resolution |
|---|---|---|
| C# 14 / net10.0 | Unity compiles `-langversion:9.0`, `netstandard2.1` (T, in Bee's rsp and the generated csproj); CoreCLR/new C# is 6.8 (R) | Core test csproj pins `LangVersion 9.0`; rules needing C# 10+ (IDE0161 file-scoped namespaces, etc.) off in Unity scope; `required` (C# 11), primary constructors (12), collection expressions (12), file-scoped namespaces (10) do not compile in Unity (J from the language versions; `init` is C# 9 but needs an IsExternalInit shim on netstandard2.1, U) |
| `Directory.Build.props` strict props | applies to generated csprojs automatically (SDK-style, T); not to Unity's own Bee compile | Condition every Unity analyzer item on `$(MSBuildProjectName.StartsWith('Game.'))` (T); keep the gate on `dotnet build` of the slnx |
| `.editorconfig` severities | ignored by Unity's compile (T); honored by dotnet build and IDEs | `Unity.globalconfig` for Unity exemptions: dotnet reads it through `GlobalAnalyzerConfigFiles`, Unity through `-analyzerconfig` in an .rsp. T precedence: an ID-level `none` in the globalconfig beats the bulk `dotnet_analyzer_diagnostic.severity = warning` in .editorconfig |
| TreatWarningsAsErrors | dotnet side only; editor side `-warnaserror+` via Assets/csc.rsp (T) | both |
| `Nullable enable` | editor: `-nullable:enable` in Assets/csc.rsp (T). Unity objects are not nullable-aware at runtime (fake null); `[SerializeField] T x;` is "never assigned" | the profile bans `!`/`= null!` outside tests; a serialized reference needs `= null!` in Unity code, so give the Unity folder a path-scoped Nullable.Extended exemption (J, U) |
| SDK global.json pin | the editor bundles SDK 10.0.303 (`Contents/Resources/Scripting/DotNetSdk`) and compiles with it via Bee; `dotnet build` uses the host SDK. Not Godot's "editor resolves the other dotnet" trap, because Unity's gate compile does not read global.json (T: not observed to) | dotnet.toml `installs` check stays for the host SDK only |
| Meziantou / Roslynator / Sonar | message methods, serialized fields, fake null, ConfigureAwait: 15 IDs fire (T, section 5) | exempt by ID in Unity.globalconfig; Microsoft.Unity.Analyzers' suppressors may remove most (U) |
| IDisposableAnalyzers, ErrorProne, SharpSource, Nullable.Extended, ReflectionAnalyzers | built clean/ran on Game.Runtime; only IDISP001 (a `new StringReader` dispose-created; real finding) and EPC27/SS001 (async void) fired (T) | keep |
| BannedApiAnalyzers | editor: unusable (T); dotnet: works | `BannedSymbols.*.txt` as `AdditionalFiles` in Directory.Build.props conditioned on Game.* |
| NsDepCop | per-project config only; all generated csprojs share a folder | U / not adopted for Unity; asmdef graph is the layer rule |
| ArchUnitNET | dotnet test project over built assemblies | U |
| xunit.v3 + MTP | works on linked Core sources (T); can't run Unity types | UTF for engine code |
| CSharpier | works (T) | keep, ignore engine folders |
| typos | not run on Unity trees here (U); needs an ignore for generated YAML/meta | add `extend-exclude` for `*.meta`, `*.unity`, `*.prefab`, `*.asset`, Library |
| NuGet lock files, CPM | N csprojs in one folder: lock-file collision; PackageReference injection needs central versions (U) | set `NuGetLockFilePath` per project |

## 5. Analyzer findings on Unity-shaped code (T)

Planted in `Game.Runtime/Hud.cs`: `[SerializeField]` fields, a public field, `GetComponent` in `Update`, `async void Start`, `StartCoroutine`, `OnTriggerEnter`, `== null` on a Unity object, `gameObject.tag == "Player"`, `Task.Delay`. `dotnet build Game.Runtime.csproj` with the full strict set fired: CA1016 CA1051 CA1822 CA1823 CA2007 CS0649 EPC27 IDISP001 MA0004 MA0006 MA0038 MA0040 MA0075 MA0084 NSDEPCOP03 RCS1146 RCS1169 RCS1213 S2325 S3168 SS001 VSTHRD100 VSTHRD111. Dispositions are in `unity.toml` architecture install. Not fired though expected: Roslynator/Sonar on missing `CompareTag` (that is Microsoft.Unity.Analyzers UNT0028-type territory, U), anything about `GetComponent` in `Update` (also UNT-type), `Camera.main` caching.
`CA1508` fired on PlayMode test code `go == null` after Destroy: a fake-null false positive.

## 6. Refused options

| Option | Why |
|---|---|
| Unity 6000.0 LTS, 6.4-6.6 update releases, 6.7 beta as the pin | support ends / short support / not released (section 1) |
| Analyzer DLLs at `Assets/` root | run on package assemblies too (T) |
| `.editorconfig` as the Unity severity file | Unity ignores it (T) |
| BannedApiAnalyzers inside the editor | naming constraint cannot be satisfied (T) |
| NsDepCop with one config for all Unity projects | one-config trap (T, same as Godot research) |
| A text/regex scanner for scripts references (`m_Script` GUID) | unresolvable package GUIDs on a clean clone (J) |
| dotnet format, StyleCop, Roslynator.Formatting | unchanged from the dotnet profile (CSharpier owns layout) |
| UnityYAMLMerge git driver | untested and hung in the trial (T) |
| Hand-written `.meta` files / editing `.meta` by agents | new GUID or broken YAML; Unity writes them |
| Any hook that starts the editor | seconds-to-minutes; gate does it |

## 7. What the shelf needs (for the owner; nothing done)

1. `profile.py`: Unity marker with root = grandparent (section 2); add `Library` to the skipped folders.
2. A shelf-shipped `unity_integrity.py` (or a blueprint tool) rather than a copy per repo; it is stdlib, 80 lines, tested here.
3. `concerns/stack.py` ROLES/FRAMEWORK_ROLES need no change; `judge_role` treats `{root}` fine. The profile's analyzer rows live in the `architecture` role because FRAMEWORK_ROLES has no linter row (Godot did the same with `.editorconfig` exemptions). The dotnet.toml `linter` role config checks `.editorconfig` for `IDE0010`/`category-Style` etc.; that stays satisfied by the repo-wide `.editorconfig`.
4. `templates/agents/unity.md` from `unity.md` (replace `{{unity_root}}`), plus link line in AGENTS.md.
5. Re-run the lab on 6000.3.x LTS before changing status from provisional; the first consumer's Library-warm vs cold timing will decide the CI cache plan.

## 8. Lab log (scratchpad `unity/lab`)

t1 EditMode pass; t2 failing test exit 2; t3 compile error exit 1, no XML; t4 missing script exit 3; t5-t6 meta behaviour (cold vs warm Library); t8-t17 analyzer scope, severity, rsp, additionalfile; t18 NsDepCop; t19 strict set under dotnet; t20 PlayMode + Awaitable + fake null; t21 player build; t22 slnx regeneration; t23-t24 rsp forwarding; t26-t28 shader. Not run: Microsoft.Unity.Analyzers, 6000.3 editor, any Hub CLI, Windows/Linux, prek, GameCI, UnityYAMLMerge success path, Addressables, IL2CPP.
