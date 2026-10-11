# shelf-1y4.17: prove the godot profile on lifesim (tests, scene integrity)

Verdict: tests = GoDotTest, SEEN RED AND GREEN on a scratch copy of lifesim (acceptance criterion met on a copy, not on lifesim itself: the repo is read-only for this task). GdUnit4Net refused as default. Scene integrity = check_godot.py plus the ERROR: scan. .uid check = done. Profile status: keep `provisional` (second Godot repo does not exist yet).

GoDotTest 2.0.47 (chickensoft-games/GoDotTest; releases 2026-08-15/08-18/09-09; MIT):
- tested: Godot 4.7.2 .NET headless, net10.0, lifesim's MTP-only global.json and strict props. Entry node + one test that loads NeedPanel.tscn and checks the tree. `godot --headless --path src/Game.Godot res://viewtests/TestEntry.tscn --run-tests --quit-on-finish`: green exit 0 in 1.2 s; planted failing assertion exit 1 ("Passed: 0 | Failed: 1").
- hazards seen (a bare exit code is not a gate): a scene with a broken ext_resource still passes with exit 0 and only ERROR: lines show it; no `--run-tests`, a renamed entry scene, or a scene that fails to load runs ZERO tests. Recipe drafts/godot-test.just fails on all of them (seen red x3). This is the same "silently skipped" hazard lifesim-bpv names for GdUnit.
- strict-stack fallout, all hit and fixed: NsDepCop default-deny needs allow lines for the test namespace; S1075 on `res://` literals (const field); tests compile into the game assembly (export filter); `System.Threading` using already removed per csproj.
- untested: coverage of in-engine tests; `[Test]` setup/teardown, async, scene runner API depth; a test needing a window (headless only).

GdUnit4Net (godot-gdunit-labs/gdUnit4Net; gdUnit4.api 5.0.0, adapter 3.0.0):
- tested: `dotnet test --solution` under MTP-only global.json REFUSES a project using it: "All projects must use that test runner. The following test projects are using VSTest runner". Non-engine logic runs via `dotnet vstest <dll>` (1 passed). Engine-runtime ([RequireGodotRuntime]) tests not run.
- read (GitHub API/README, 2026-10-11): README targets Godot 4.4; last stable v5.0.0 2025-06-21; 5.1.0 is rc5 (2026-06-21, rc1 2025-09-18); repo active (commits to 2026-07); no MTP mention in repo search. Refused as default for that reason; revisit if an MTP adapter ships. Unblocks lifesim-bpv: pick GoDotTest.

Scene integrity: see report-shelf-d89.md (import log is blind outside main scene/theme; check_godot.py seen red on 9 plants incl. missing .uid, uid mismatch, version skew; green on lifesim's real files). Cold-import false-red finding is the most urgent lifesim fix.

Not done / honest limits: nothing was committed or edited in lifesim; GoDotTest not run in CI (shelf-bif no-ci); second-repo evidence absent; `.uid` and version checks are python scripts (custom checks the bead expected).
