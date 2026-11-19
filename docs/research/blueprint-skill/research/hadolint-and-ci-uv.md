# shelf-1y4.20 hadolint, shelf-3qq setup-uv and the uv pin (2026-10-11)

Evidence key: tested = run here (Linux x86_64, no Docker, scratch copies); read = fetched or read; untested.

## A. hadolint
Verdict: its own small stack profile, `profiles/dockerfile.toml`, not a compose role.
- Why: a2kay has `Dockerfile` and `scripts/prune/test.Dockerfile` and no compose file (read), so a compose-conditional role would never fire there. Compose and Dockerfile are independent: a compose file says nothing about images built from source.
- Detection: `Dockerfile`, `*.Dockerfile`, `Dockerfile.*` (not `*.dockerignore`: a2kay has `test.Dockerfile.dockerignore`), `Containerfile`, within 3 levels, one table per repo.

| fact | evidence |
|---|---|
| hadolint 2.15.1, released 2026-07-31, a static binary | read (GitHub API), tested (`--version`) |
| homelab images/devbox: exit 1 (DL3008, DL4006); images/frigate: exit 1 (DL3008, DL3013) | tested |
| a2kay Dockerfile: exit 1 (2x DL3008); scripts/prune/test.Dockerfile: exit 1 (DL3008 x2, DL4006, DL3022 x4) | tested |
| the shelf's tools/gate/gate.Dockerfile: exit 1 (DL3008, DL4006); green after `SHELL [... pipefail]` per stage and DL3008 ignored with a reason | tested |
| a planted `FROM ubuntu:latest` with `apt-get install curl`: exit 1, DL3007 DL3008 DL3014 DL3015 | tested |
| `--failure-threshold error` on devbox (warnings only): exit 0 | tested |
| `.hadolint.yaml` `ignored: [DL3008]` drops that finding; DL4006 still exits 1; config read from the cwd | tested |
| DL3022 on a2kay is a false positive: `--from=shelf` is a `--build-context`, not a FROM alias | read, plus the finding seen |
| hadolint does not carry `SHELL` across stages (Docker does): a stage that pipes needs its own | tested on the shelf's file |
| info-only findings vs the threshold; inline `# hadolint ignore=` comments | untested |

## B. setup-uv and the uv pin
Verdict: the first release that reads `required-version` (uv.toml, then pyproject.toml) when `version:` is omitted is **astral-sh/setup-uv v5.2.0 (2025-01-16)**. Evidence: read, bisected on the README at each tag (v3.x, v4.x, v5.0.0-5.1.0 do not mention it; v5.2.0 does). The action source was not read, so the README is the claim.
- `.tool-versions` is read only through the `version-file:` input, from v6; mise.toml never. A `>=` range resolves with `resolution-strategy: highest` (the default), so `>=0.13.0` installs the newest uv, not 0.13.0. The latest setup-uv is v10.3.0 (2026-10-09).
- Both consumers then: the shelf's check.yml ran setup-uv `# v3` with no version (the newest uv; v3 ignores required-version) and then jdx/mise-action `--locked` (the mise pin), so `uv sync` ran on the newest uv; a2kay's ci.yml runs setup-uv `# v3` with `version: "0.13.0"`, beside a comment that mise.toml pins the same uv. The shelf's gate image copied uv 0.10.12.
- a2kay images: `scripts/prune/test.Dockerfile` copies `ghcr.io/astral-sh/uv:0.13.0` (the pin); the root `Dockerfile` copies `uv:latest`.

Built as `stack.python-uv.uv-ci`. The pin is mise.toml's `uv` if present, else an exact `==X.Y.Z` required-version.
1. Each setup-uv step either sets `version:` equal to the pin, or is v5.2.0 or later with no `version:` and an exact required-version. Below v5.2.0 with no version, or a range floor, installs the newest uv: a finding. jdx/mise-action installs the mise pin and needs nothing.
2. Each `COPY --from=ghcr.io/astral-sh/uv:<tag>` equals the pin (a digest after the tag is allowed); `latest` or no tag is a finding.

Untested: reusable-workflow installs; a SHA-pinned ref whose version is only in its `# vX` comment is read from the comment.
