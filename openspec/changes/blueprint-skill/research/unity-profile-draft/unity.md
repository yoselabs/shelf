# Unity conventions

Framework layer on top of [dotnet.md](dotnet.md) for a Unity 6 C# game. `{{unity_root}}` is the folder holding `ProjectSettings/`.
Unity compiles at C# 9 (`netstandard2.1`) through 6000.7; rules that need newer C# do not apply to Unity code.
Draft note: a rule marked (seen) was reproduced on 6000.7.0b4; the rest is engine knowledge from Unity docs, not re-run here.

## Tools per role

| role | tool | enforced by |
|---|---|---|
| framework-version | `ProjectSettings/ProjectVersion.txt` (newest LTS stream); `Packages/packages-lock.json` committed | config check, build target compares `Unity -version` |
| project-hygiene | `Library/ Temp/ Logs/ UserSettings/` ignored; every asset has a committed `.meta`; Force Text; Visible Meta Files | `tools/unity_integrity.py`, clean tree after import |
| binary-assets | Git LFS patterns in `.gitattributes`; never LFS for `.meta .unity .prefab .asset .mat` | config check |
| build | `Unity -batchmode -nographics -quit -projectPath {{unity_root}}`; exit 1 = C# compile error | gate |
| tests | `-runTests` EditMode and PlayMode, results XML must exist and say Passed; pure core tested with `dotnet test` | gate |
| surface-integrity | `CiValidate.Run`: no missing script in any scene or prefab (exit 3) | gate |
| architecture | one `.asmdef` per layer, explicit `references`, `noEngineReferences` on the core | compiler, `dotnet build` of the generated solution |
| analyzers | strict .NET set on `Game.*` generated projects, exemptions in `Assets/Unity.globalconfig` | `dotnet build -warnaserror` |
| hooks | prek `unity-integrity`, `csharpier check` | hook |
| embedded-script-lint | none proven for shaders | - |
| ci | none for now: agents run `make check` where the pinned editor is installed (`UNITY` var) | - |

## Run

```bash
make check          # unity-build, unity-test, unity-validate, dotnet build + test, integrity script
make unity-build    # compile + import; then the tree must be clean
make unity-test     # EditMode + PlayMode; read results-*.xml
make unity-validate # missing scripts in scenes and prefabs
```

The editor in `ProjectVersion.txt` must be installed; any other version fails the gate. Close the editor GUI first: a project open in
one editor cannot be opened by a second.

## Rules

| rule | why |
|---|---|
| Never hand-edit `.meta`, `Library/`, `Temp/`, `UserSettings/`, generated `*.csproj` / `*.slnx` | Unity regenerates them; a hand edit is lost or corrupts GUIDs |
| A new, moved or renamed asset moves with its `.meta` in the same commit; move files with `git mv` on both | A `.meta` carries the GUID every scene and prefab references |
| Never delete a `.meta` to "fix" something | On a cold Library Unity assigns a NEW GUID and every reference breaks (seen) |
| Scenes and prefabs are YAML: never reformat, never merge by hand | Diff noise and silent breakage; ask the owner, do not guess |
| No game rules in `MonoBehaviour`s: behaviours read state from the core and send commands | The core stays testable without the editor |
| The core assembly sets `noEngineReferences: true`; no `UnityEngine` there | Compile error, and `dotnet test` can run it |
| Every new `.asmdef`: `autoReferenced: false`, references listed by name | The asmdef graph IS the layer map |
| `// why:` for engine quirks with a link | The scene is the source of truth for structure |

## Layout

| thing | where |
|---|---|
| Engine-free logic | `Assets/Scripts/Core/` (`Game.Core.asmdef`, `noEngineReferences`), linked into `tests/<Name>.Core.Tests` |
| MonoBehaviours, ScriptableObjects | `Assets/Scripts/Runtime/` (`Game.Runtime.asmdef`, references Core) |
| Editor tools, CI entry points | `Assets/Editor/` (Editor-only asmdef): `CiValidate`, `CiBuild` |
| Tests | `Assets/Tests/EditMode`, `Assets/Tests/PlayMode` (own asmdefs, `UNITY_INCLUDE_TESTS`) |
| Analyzer config | `Assets/Unity.globalconfig`, pointed at by `Assets/Scripts/*/<Asm>.rsp` and `Directory.Build.props` |

## Null: the fake-null trap

`UnityEngine.Object` overloads `==`. A destroyed object compares `== null` true while the C# reference is not null (seen in PlayMode).

- Test a Unity object with `obj == null` or `obj` in a boolean (Unity overloads). Never `obj is null`, `obj ?? other`, `obj?.Member`, `obj!`: they check the C# reference, not liveness.
- For non-Unity types use `is null` as the .NET profile says.
- The analyzers that suggest `?.`/`??` (RCS1146, IDE0031, IDE0270) are off in the Unity scope for this reason; CA1508 is off because it calls `go == null` after `Destroy` "always false".

## Serialization

- Unity serializes public fields and `[SerializeField]` private fields; NOT properties, `static`, `readonly`, `const`, dictionaries (until Unity ships it), interfaces, abstract types.
- `[SerializeField] private T x;` for inspector data; never a public field for it. The analyzer set exempts the "never assigned" warning, so check yourself: an unassigned serialized reference is null at runtime.
- Renaming a serialized field loses its value; add `[FormerlySerializedAs("old")]`.
- Use `[SerializeReference]` only with a reason; polymorphic data is hard to merge.

## MonoBehaviour traps

- `Awake` -> `OnEnable` -> `Start`; `Awake` of other objects may not have run yet. Do not read another component in `Awake`; wire in `Start` or inject.
- No constructors and no field initialisers that call the engine API; Unity constructs the object itself during deserialization, so the engine API is not safe there. `new MyBehaviour()` is wrong: `AddComponent`.
- `Update` is hot: no `GetComponent`, `Find*`, `Camera.main` (cache in `Awake`), no LINQ, no string concat, no `gameObject.tag == "x"` (`CompareTag`).
- Message methods (`Update`, `OnTriggerEnter`) are private and look unused or static to analyzers; the exemptions are in `Assets/Unity.globalconfig`. Do not "fix" the warning by making them `static`.
- `Destroy` is deferred to end of frame; the object is still there for the rest of the frame (fake null applies after).
- Coroutines die with the object being disabled or destroyed; `StartCoroutine` on an inactive object throws.

## Domain reload and statics

- With Enter Play Mode Options (domain reload off), statics and events survive between runs. Reset them in `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]`.
- Editor-only code goes in an Editor asmdef (or `#if UNITY_EDITOR`); `UnityEditor` in a runtime asmdef breaks the player build, not the editor.
- Script compile and domain reload happen on every change; a long `make` loop in an open editor will fight it. Run the gate with the editor closed.

## Async

- Prefer `async Awaitable` (Unity's pooled awaitable, runs on the main thread; `async Awaitable Start()` ran in PlayMode, seen) over `async void` or `Task` for engine work.
- Pass `destroyCancellationToken` into every awaited call in a behaviour (MA0040 asks for it). Never `ConfigureAwait(false)` in Unity code: it leaves the main thread.
- `async void` is a gate failure everywhere except an engine event with no alternative; say why in a `// why:`.
- Threads: Unity API only on the main thread; `Awaitable.BackgroundThreadAsync()` and `MainThreadAsync()` switch.

## Addressables and assets

- Load by address or `AssetReference`, release what you load; `Resources/` folders are shipped whole, avoid.
- Addressables groups are committed (`Assets/AddressableAssetsData/`); a broken group is not caught headless in this setup (untested).

## Analyzer traps

- Exemptions live only in `Assets/Unity.globalconfig` (one ID per line with a reason). Never `#pragma` / `SuppressMessage`.
- `.editorconfig` is ignored by Unity's own compiler; the globalconfig + `.rsp` is what it reads. Both files feed `dotnet build`.
- The generated `*.csproj` set differs from the editor compile only in analyzers and `NoWarn` (CS0649 is muted in the editor, not in dotnet).
- BannedApiAnalyzers and NsDepCop do not run in the editor compile (their config files cannot reach it); they run in `dotnet build`.
