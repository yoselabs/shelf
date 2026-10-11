import re,tomllib
src=open('~/Workspaces/shelf/packages/blueprint/src/blueprint/profiles/frameworks/godot.toml').read()
blocks=re.split(r'(?m)^(?=\[\[role\]\]\n)',src)
head,roles=blocks[0],blocks[1:]
def name(b): return re.search(r'role = "([^"]+)"',b).group(1)
new={}
new['binary-assets']='''[[role]]
role = "binary-assets"
tool = """Git LFS for every binary blob, proven by a deterministic check, not by a pattern list: `git ls-files --eol` marks a blob git sees as binary `i/-text`, and each such path must carry `filter: lfs` (`git check-attr filter`). \\
.gitattributes patterns (png, jpg, webp, wav, ogg, mp3, glb, ttf, otf, exr, hdr, blend, fbx, bin, ...) are the setup; the check is what catches an extension nobody listed. export_presets.cfg committed, credentials only in .godot/export_credentials.cfg. \\
Upload under prek is proven: a local pre-push hook `git lfs push --all "$PRE_COMMIT_REMOTE_NAME"` sent all 19 LFS objects to a bare file:// remote and a fresh clone checked out real content (git-lfs 3.7.1, prek, macOS; bead shelf-d89 comment, 2026-10-11)"""
install = """.gitattributes: `*.png filter=lfs diff=lfs merge=lfs -text` for each binary extension in the repo; `git lfs install --skip-repo` (prek owns the hooks); .pre-commit-config.yaml local hook id git-lfs-push (entry sh -c 'git lfs push --all "$PRE_COMMIT_REMOTE_NAME"', always_run, pass_filenames false, stages [pre-push]); CI checkout with `lfs: true`. \\
justfile recipe `lfs-check` (shebang recipe, no backticks in the file): `bad=$(git ls-files --eol | grep '^i/-text' | cut -f2 | git check-attr --stdin filter | grep -v 'filter: lfs'); test -z "$bad" || { echo "binary outside LFS:" >&2; echo "$bad" >&2; exit 1; }` (the pipe filters on git's own text/binary verdict; LFS pointer files are text in the index, so a correctly tracked asset never appears). \\
Seen red on lifesim (read-only git): design/research/character-pipeline-spike/sliders-live.mp4 is a binary blob with `filter: unspecified` (mp4 was in no pattern); every other binary there is LFS"""
config = [
    { path = ".gitattributes", contains = "filter=lfs" },
    { path = ".pre-commit-config.yaml", contains = "git lfs push" },
]
gate = "check-attr"
'''
new['tests']='''[[role]]
role = "tests"
tool = """Chickensoft GoDotTest 2.0.47 (MIT; releases 2026-08-15, 2026-08-18, 2026-09-09) runs C# tests inside the engine headless: `godot --headless --path <root> res://viewtests/TestEntry.tscn --run-tests --quit-on-finish`. \\
Seen green (exit 0, 1.2 s) and red (planted failing assertion: exit 1) on a scratch copy of lifesim with the strict analyzer set and warnings as errors, Godot 4.7.2 .NET, net10.0, MTP-only global.json (it is not a VSTest or MTP project, so there is no clash). \\
The gate must also read the log: a broken ext_resource in the scene under test leaves the exit code at 0 (only ERROR: lines show it), and a missing --run-tests, a renamed entry scene or a scene that fails to load runs zero tests and exits 0, so the recipe fails on any ERROR: line and when `Test results: Passed: N` has N < 1 (all seen red). \\
Engine-free logic stays in the xunit.v3 projects; in-engine tests only for thin views. Refused: GdUnit4Net 5.0.0 (godot-gdunit-labs/gdUnit4Net) as the default, see the install note"""
install = """Directory.Packages.props <PackageVersion Include="Chickensoft.GoDotTest" Version="2.0.47" />; Game.Godot.csproj <PackageReference Include="Chickensoft.GoDotTest" />. In {root}/viewtests/: TestEntry.cs (a Node whose _Ready calls `GoTest.RunTests(Assembly.GetExecutingAssembly(), this, env)` when `TestEnvironment.From(OS.GetCmdlineArgs()).ShouldRunTests`), TestEntry.tscn, and `public class XTest(Node testScene) : TestClass(testScene)` with `[Test]` methods that `GD.Load<PackedScene>(...)`, instantiate, assert on the tree. \\
The strict stack needs three adjustments (all hit): config.nsdepcop gets `<Allowed From="Game.ViewTests.*" To="..." />` lines for Game.ViewTests, System, Godot and Chickensoft.GoDotTest (default-deny whitelist); a `res://` literal in a method trips S1075, so scene paths are `const string` fields; the tests compile into the game assembly, so export_presets.cfg excludes `viewtests/*` from the exported pack. justfile recipe `godot-test` (drafts/godot-test.just, tested with just 1.58): runs the command, strips ANSI, fails on ERROR:, fails when no `Passed: [1-9]`, else returns the engine's exit code; add it to `check`. \\
GdUnit4Net, tested: its VSTest adapter makes `dotnet test --solution` refuse the solution under global.json's Microsoft.Testing.Platform runner (message: All projects must use that test runner. The following test projects are using VSTest); non-engine logic tests do run through `dotnet vstest <dll>` (1 passed), an engine-runtime test was not run. README targets Godot 4.4; last stable v5.0.0 2025-06-21, 5.1.0 has been a release candidate since 2025-09 (rc5 2026-06-21). It becomes an option only if MTP support lands"""
config = [
    { path = "Directory.Packages.props", contains = "Chickensoft.GoDotTest" },
    { path = "{root}/viewtests/TestEntry.cs", contains = "ShouldRunTests" },
    { any = [{ path = "justfile", contains = "--run-tests" }, { path = "Makefile", contains = "--run-tests" }] },
]
gate = "--run-tests"
'''
new['surface-integrity']='''[[role]]
role = "surface-integrity"
tool = """tools/check_godot.py (stdlib python, no editor): every .tscn/.tres has a valid header and no garbage line, every ext_resource path exists and its uid equals the target's .uid/.import/header uid, every ExtResource/SubResource id is declared, no ext_resource is unused; every .cs/.gd/.gdshader has its .uid; Godot.NET.Sdk major.minor equals project.godot config/features. \\
Why not the import log alone: `godot --headless --import` only loads what the editor loads (run/main_scene and gui/theme/custom). Tested on 4.7.2 against a scratch copy of lifesim: a broken script ext_resource, a garbage line or an undeclared ExtResource in NeedPanel.tscn (not the main scene) printed NO error; the same broken ext_resource in the main scene or theme.tres did, but a garbage line in the main scene did not. The script was seen red on all of these plus a missing .uid, a bad uid and a version skew, green on lifesim's 6 scenes/resources (theme.tres is 900+ lines). \\
Known gap: the script cannot see a wrong resource type or an unknown node class; only the engine can, so the ERROR: scan of the import (build row) and of the test run (tests row) stay"""
install = """copy drafts/check_godot.py to tools/check_godot.py; justfile: `godot-surface:` `python3 -I tools/check_godot.py {root} {root}/Game.Godot.csproj`, in `check` (needs no Godot binary, so it also runs where the editor is absent). Run with `python3 -I` so a stray module in the folder cannot shadow the stdlib"""
config = [
    { path = "tools/check_godot.py" },
    { any = [{ path = "justfile", contains = "check_godot" }, { path = "Makefile", contains = "check_godot" }] },
]
gate = "check_godot"
'''
out=[new.get(name(b),b).rstrip('\n')+'\n' for b in roles]
txt=head+'\n'.join(out)
a='both inside just check; the import log is scanned for ERROR lines and the tree must stay clean'
assert a in txt
txt=txt.replace(a,'both inside make check; the SECOND import log is scanned for ERROR lines (the first pass of a fresh clone prints about 190 false ERROR lines) and the tree must stay clean')
b='runs `"{{godot}}" --headless --path {root} --import 2>&1 | tee import.log`, then'
assert b in txt, 'build install anchor'
txt=txt.replace(b,'runs `"{{godot}}" --headless --path {root} --import >/dev/null 2>&1` once to warm .godot/ (a cold first import prints about 190 ERROR lines on a clean repo: `Unable to open file: res://.godot/imported/*.ctex`, and theme font references parsed before the font is imported; seen on a fresh copy of lifesim, Godot 4.7.2, 2026-10-11; the second pass is clean), then AGAIN as `"{{godot}}" --headless --path {root} --import 2>&1 | tee import.log`, then')

old_cfg='config = [{ any = [{ path = "justfile", contains = "--build-solutions" }, { path = "Makefile", contains = "--build-solutions" }] }]\ngate = "--build-solutions"'
assert old_cfg in txt, "build config anchor"
txt=txt.replace(old_cfg,'config = [\n    { any = [{ path = "justfile", contains = "--build-solutions" }, { path = "Makefile", contains = "--build-solutions" }] },\n    { any = [{ path = "justfile", contains = "ERROR:" }, { path = "Makefile", contains = "ERROR:" }] },\n]\ngate = "--build-solutions"')
open('godot.toml','w').write(txt)
d=tomllib.loads(txt);print([r['role'] for r in d['role']])
