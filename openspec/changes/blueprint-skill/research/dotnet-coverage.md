# dotnet coverage role (shelf-8eg)

Adopted into profiles/dotnet.toml (coverage role) and the `dotnet-coverage` recipe (recipes/check_coverage.py).

Verdict: DONE, seen red and green UNDER MTP on a scratch copy of lifesim (the bead's own premise was wrong in one place). Real repo untouched; ran `dotnet test` on a copy, .NET SDK 10.0.401, macOS arm64, strict analyzer set + warnings as errors, xunit.v3 on Microsoft.Testing.Platform (MTP-only global.json).

Answer (drafts/dotnet-coverage-role.toml, merged into drafts/dotnet.toml): coverlet.MTP 10.1.0 (MIT, released 2026-09-27) collects cobertura; ReportGenerator 5.5.11 merges the per-project reports (JsonSummary); drafts/check_coverage.py fails under a committed coverage-floor.json {"line","branch"}. Single-test-project repos can use coverlet's own threshold.

Evidence:
- tested: `--coverlet-threshold 90 --coverlet-threshold-type line,branch --coverlet-threshold-stat total` exits 14 under, 0 over, both directly and through `dotnet test`. The package's own docs (Coverlet.MTP.Integration.md line 446, "Threshold validation is not yet supported") are stale; the option is implemented. `dotnet test` hides the reason (run the exe for the "Coverage Threshold Results" block).
- tested on lifesim copy: 3 test projects, 119 tests green with coverlet.MTP added (build clean under latest-all, warnings as errors). Merged first-party coverage 89.9% line, 75.7% branch. Floor 89/75 green; floor 95 red (exit 1); planted regression (one test file removed, 91 tests) -> branch 74.2% < 75 red.
- gotchas, all seen: no `--coverlet-include '[Sim.*]*'` gives 23.5% (NuGet assemblies such as Humanizer count); default stat is Minimum, so Sim.Maths at 0% would fail a per-project threshold; an architecture-test project covers ~0% so a per-project threshold cannot be a multi-project floor; `--results-directory` after `--` crashed dotnet test; output lands in ./TestResults when run with --solution.
- tested: Microsoft.Testing.Extensions.CodeCoverage 18.12.0 works on macOS arm64 (`--coverage --coverage-output-format cobertura`), same numbers as coverlet on a toy project; it has no threshold option. Kept as fallback, not default (closed engine, needs the same script).
- ReportGenerator has no threshold switch (`-h` checked), hence the script. Not asked: branch floor policy and the ratchet commit rule are my design.

Refused: coverlet.collector/msbuild (VSTest/MSBuild paths, wrong under MTP-only); a per-project threshold as the repo floor (above); NetArchTest-like duplicates not relevant.

Open: lifesim's own `stack.dotnet.coverage` row stays unjudged until a `coverage` recipe + files are committed in lifesim (I did not edit it). Gate string is `check_coverage`; engine tests added for pass and outside-the-gate fail.

Update 2026-10-29 (owner ruling: accept both). Microsoft.Testing.Extensions.CodeCoverage 18.12.0 is now an accepted collector beside coverlet.MTP (the coverage role's config takes either); coverlet stays the default for a new repo. Evidence, measured on lifesim's devbox at one commit (8eba69464), build included: `just coverage` 5m42s with coverlet.MTP vs 4m36s with the Microsoft extension (tests alone 5m15s vs 3m57s); line coverage 94.1% both; branch 85.2% vs 86.8%; no source file covered under coverlet is missing from the new report. Sim.Properties alone: no coverage 125 s, coverlet 209 s, Microsoft 133 s. Trade-off unchanged: closed-source engine, no threshold option, so the same check_coverage.py floor script is needed.
