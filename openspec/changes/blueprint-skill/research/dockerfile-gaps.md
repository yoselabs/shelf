# dockerfile.toml gaps: formatter, dependencies, tests (2026-10-11)
Evidence key: T = run here (Linux x86_64, no Docker daemon, scratch copies of 5 real Dockerfiles from 3 repos); R = read (web/API/file); U = untested.
Files: proposed-roles.toml (3 role blocks), check_dockerfile_pins.py (recipe), image-job.yml (CI job).

## Verdicts
| role | verdict | why |
|---|---|---|
| tests | standard, land as `untested` until one CI run is linked | the incident (a COPY from a dropped Makefile, a sub-floor uv) was never built; the job below catches it. Cannot be seen red/green without a daemon |
| dependencies | standard (recipe `dockerfile-pins`) | red and green seen; updater named in the role |
| formatter | standard: dockerfmt 0.5.4, but adoption costs a reformat | red and green seen; maintained; opinionated. `na` is the fallback if a consumer refuses the reformat |

## 1 dependencies
| fact | ev |
|---|---|
| checker red (exit 1): `:latest`, bare `nginx`, ARG-built `python:${PY}-slim`, `${UNSET}`, `COPY --from=uv:0.13.0` unpinned | T |
| green (exit 0): `FROM --platform=.. $BASE AS x` with ARG default carrying a digest, `scratch`, earlier alias, stage number, `--from=shelf`, `RUN --mount=from=img@sha256`, continuation lines | T |
| real: 9 findings in a2kay x2, shelf gate, homelab frigate; homelab devbox (pinned) exit 0 | T |
| `--from=shelf`/`head` are build contexts: a bare name (no `:` `/` `@`) in COPY --from is exempt; in FROM it is not (implicit :latest). `--context NAME` for FROM-naming a context | T |
| ARG decision: substitute defaults before the first FROM; no default = finding (cannot tell what is pulled). Build-time `--build-arg` overrides are not seen | T |
| `crane digest python:3.12-slim` (0.22.1 via mise) exit 0, prints sha256; needs network + registry | T |
| hadolint has no digest rule (DL3006/3007 tag only); no maintained `dockerfile-pin` tool found | R |
| Renovate `pinDigests` (dockerfile manager) is the updater; not run here (no Renovate app/config) | U |
Where: a recipe the repo runs in its gate (RECIPE_FILES `dockerfile-pins` -> check_dockerfile_pins.py), not an engine concern. Reasons: every other per-repo tool is a recipe (godot, unity); the engine would then check the files at audit time only, not on every `just check`; config is the script + justfile hook + updater. Needs RECIPE_FILES entry + recipe copy (not made).

## 2 formatter
| fact | ev |
|---|---|
| dockerfmt v0.5.4 2026-06-27 (0.5.2 04-06), 4 open issues, not archived, shfmt inside RUN, `dockerfmt-ignore`, `--check`, `-w` | R |
| `--check`: exit 1 on planted (lower-case `from`/`run`, double spaces) and on 5/5 real files (5-55 lines each); after `-w -n` all exit 0; second `-w` no change | T |
| style choices the files do not share: indent of continuations (default 4; -i 2 differs), `&&` realigned, `> x` to `>x`, RUN --mount line split, trailing newline (`-n`) | T |
| dockerfile-utils last release 2025-07 (0.16.3); prettier-plugin-dockerfile: no npm package | R |
Cost: a one-time rewrite of every Dockerfile; shell inside RUN is rewritten (no behaviour change checked beyond hadolint, not rerun).

## 3 tests
| fact | ev |
|---|---|
| no daemon: `docker build --check`, container-structure-test, the job itself | U (not runnable here) |
| homelab build-images.yml (read): builds each images/<n>, `load: true`, runs `test.sh`, then pushes; push-to-main + dispatch only, no PR | R |
| a2kay ci.yml (read): pull_request + push main; no image job; `a2kay --version` existence not confirmed in src | R, U |
| action SHAs: setup-buildx v4.4.1 f87e599..., build-push v7.4.0 c3c9e26... (API tag lookup; homelab pins v3.12.0/v6.19.2) | R |
Product vs test image: product = shipped or deployed (a2kay root Dockerfile, homelab images/*); test = needs extra build contexts or bakes in the gate (a2kay scripts/prune/test.Dockerfile, shelf tools/gate/gate.Dockerfile): exempt, exercised by the gate that runs it.
Engine check (config): any workflow has `docker/build-push-action` or `docker build`, AND any has `docker run` or `test.sh`. Both shapes match; two entries are not tied to one file (weak, accepted). The trigger is NOT checked (engine cannot tell a direct-to-main repo): the role says pull_request is the standard, push-to-main accepted where the repo merges straight to main, said in the workflow.
Missing evidence: a green run on a2kay's real image, and a red one on a planted bad COPY.

CI evidence, 2026-10-12 (a temporary shelf branch, deleted after): run 38184048761 built a good image and ran its smoke green, and saw a COPY of a missing file fail the build and an image that cannot start fail its smoke; run 38185504352 built the shelf's own tools/gate/gate.Dockerfile (13.5 min, cold cache) and ran `just --dry-run check-host` in it. The `tests` role is a standard on this evidence; the shelf's check.yml carries the gate-image job.
