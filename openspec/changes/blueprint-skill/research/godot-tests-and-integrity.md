# Godot profile: tests, scene integrity, LFS (shelf-d89, shelf-1y4.17)

Adopted into profiles/frameworks/godot.toml and the `godot-integrity` and `godot-test` recipes. The two research reports follow.

## shelf-d89: godot profile, remaining roles

Verdict: DONE for tests, surface-integrity, binary-assets, embedded-script-lint; build row corrected (a lifesim false-red found). CI stays shelf-bif's declared no-ci trait (not touched). Profile stays `provisional` (one Godot repo). Drafts: drafts/godot.toml (full file at shelf HEAD 7e082d1), godot-test.just, check_godot.py. Tested on a scratch copy of lifesim (src/Game.Godot) with Godot 4.7.2.stable.mono, nothing in lifesim edited.

- tests: Chickensoft GoDotTest 2.0.47. tested green (exit 0, 1.2 s) and red (planted failing assertion exit 1; broken scene -> exit 0 but ERROR: lines; renamed entry or missing --run-tests -> zero tests, exit 0). The `godot-test` justfile recipe fails on ERROR:, on no `Passed: [1-9]`, else passes the exit code; all three seen red. Compiles clean under lifesim's strict analyzers after: NsDepCop allow lines for Game.ViewTests, scene path as const (S1075). Costs: tests live in the game assembly (exclude `viewtests/*` from export). Detail and GdUnit4Net verdict in report-shelf-1y4.17.md.
- surface-integrity: `godot --headless --import` is NOT enough. tested: it reports errors only for what the editor loads (main scene, project theme). A broken script ext_resource, a garbage line, an undeclared ExtResource in NeedPanel.tscn (not main) printed nothing; a garbage line in the main scene printed nothing. The old profile's "seen red on a bad scene line" is wrong. New check_godot.py (stdlib, no editor): header, garbage line, ext_resource path exists and uid matches, ids declared, unused ext_resource, .uid sibling for every .cs/.gd/.gdshader, csproj Sdk version vs project.godot features. Seen red on 9 plants, green on lifesim's 6 scenes/resources. Gap: wrong resource type / unknown node class (engine only) stays on the ERROR: scan.
- build (found while testing): a cold `--import` on a clean copy printed 193 false `ERROR:` lines (Unable to open .godot/imported/*.ctex; theme.tres font "non-existent" before the font is imported); the second pass was clean. So lifesim's godot-build is red on a fresh clone. Profile now says: import twice, scan the second log. Not yet seen end-to-end in a recipe.
- binary-assets: tested read-only on lifesim: `git ls-files --eol | grep '^i/-text' | cut -f2 | git check-attr --stdin filter | grep -v 'filter: lfs'` flags design/research/.../sliders-live.mp4 (binary, no LFS pattern; mp4 not in the list). LFS push-under-prek proof from the bead comment is in the role text (git-lfs 3.7.1, prek, 19 objects, bare file://, 2026-10-11): cited, not re-run.
- embedded-script-lint: stays `na` while no .gd. Engine suggestion (not drafted): an `na_unless_glob = "**/*.gd"` field so the row flips to mandatory (gdtoolkit 4.5.0, quiet since 2025-10, untested on 4.7 syntax) the day a .gd appears.
- .uid check: check_godot.py (gate) + existing godot-uid prek hook (staging). Tested red on a missing .uid.
- Config paths now accept justfile or Makefile (the gate runner is just since commit 7e082d1).

## shelf-1y4.17: prove the godot profile on lifesim (tests, scene integrity)

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
