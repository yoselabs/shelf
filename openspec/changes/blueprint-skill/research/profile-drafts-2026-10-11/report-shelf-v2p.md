# shelf-v2p: nix and compose stack profiles (homelab)

Verdict: DONE as drafts. `nix.toml` and `compose.toml` + a 10-line detection change; run on a scratch copy of homelab the engine reports both stacks and the gate rows the bead asks for (nix types = "set up, `just check` never runs it"). Compose is a STACK, not a framework (framework detection yields one table per marker folder = 19 tables on homelab; stack detection yields one).

Evidence key: tested = run here (Docker `nixos/nix` Nix 2.34.7 arm64 Linux on a Mac; no local nix; Docker Compose v5.1.2; scratch copy of homelab, never the repo); read = fetched (URL, 2026-10-11); untested.

## Nix
| role | answer | evidence |
|---|---|---|
| detect | `flake.nix` within 3 levels | tested: homelab hosts/bee, hosts/sol found; engine test added |
| formatter | nixfmt 1.5.0 `--check` | tested: red on homelab (27 of 28 files not clean), exit 1; read github.com/NixOS/nixfmt releases v1.5.0 2026-09-11 |
| linter | statix check + deadnix --fail | tested: statix exit 1 (7 warnings), deadnix needs `--fail` (exit 0 without), exit 1 on homelab; clean file exits 0 |
| types | host eval `nix eval path:<repo>?dir=hosts/<h>#nixosConfigurations.<h>.config.system.build.toplevel.drvPath --raw` | tested green on bee (62 s to 3 min cold); RED on planted `enabel` (exit 1, "option services.avahi.enabel does not exist"). `nix flake check --no-build` also tested green on bee (evaluates nixosConfigurations.bee), not seen red |
| toolchain | flake.lock committed + `nix flake lock --no-update-lock-file` + pinned nix image | lock present: tested. Drift command: UNTESTED (my plant needed a GitHub fetch, hit API rate limit, failure unrelated) |
| dependencies | `follows` on every non-nixpkgs input | read in homelab flakes; engine config check only |
| tests | untested | NixOS VM tests need KVM; Docker on this Mac has no /dev/kvm |
| coverage, architecture | na, reasons in file | |
| spelling, hooks, agent-guidance | typos / prek hooks / docs/agents/nix.md | same shape as other profiles |

Refused: nixpkgs-fmt (repo archived, last push 2024-07-24; read GitHub API); alejandra 4.0.0 (maintained, last release 2025-04, but not the official RFC 166 style: a second layout opinion); upstream oppiliappan/statix as the install source: its README (read) says it moved to tangled.org and nixpkgs packages the Molybdenum fork (pushed 2026-10-09), so install from nixpkgs; release age (0.5.8, 2023-09) is not the reason, provenance is.

Homelab findings (the profile would raise): `make check` reaches only `lint` + `lint-arch`, never `check-host`; lint.yml has no nix step; tools/check-host.sh pins `nixos/nix:latest`; 27/28 .nix files fail nixfmt; statix and deadnix red.

## Compose
| role | answer | evidence |
|---|---|---|
| detect | compose.y(a)ml / docker-compose.y(a)ml within 3 levels, one table per repo | tested: 19 homelab stacks -> 1 table; engine test |
| types | `docker compose -f f config --no-interpolate -q` | tested: red on unknown key and wrong type, green on 3 real stacks. WITHOUT `--no-interpolate` real stacks fail on `${VAR:?}` (A2WEB_ZYTE_KEY) |
| dependencies | every image `@sha256:<64>` via `config --no-interpolate --format json \| jq -e` | tested: red on `nginx:latest`, green on 2 real; homelab 0 unpinned; homelab's tools/doctor.py (DIGEST_RE) already enforces it, in CI only |
| linter | dclint 3.1.0 `--max-warnings 0` (+ hadolint for Dockerfiles) | tested: red on planted file (2 errors: unbound port, `:latest`); default exit is 0 on warnings so `--max-warnings 0` is required; does NOT flag `privileged: true`. hadolint 2.15.1 (released 2026-07): red on homelab images/devbox/Dockerfile (DL3008, DL4006) |
| formatter, tests, architecture | untested | no compose formatter exists; smoke needs secrets; conftest policy candidate not run (homelab has its own tools/stack_policy.py, read only) |
| toolchain, coverage | na | Compose spec unversioned; no executable lines |

Watch item: dclint last release 2025-07-24, last real commit 2025-09 (10 months); not abandoned (issues opened through 2026-04) but one more year of silence moves the role to conftest. Hadolint needs its own conditional role (Dockerfile detection); not drafted.

Engine: `engine-and-profiles.patch` (profile.py detection + both profiles + 3 tests); the full blueprint suite (229 tests) passed with the patch applied to a scratch copy at HEAD 7e082d1 (after rebasing on the just-runner commit).
