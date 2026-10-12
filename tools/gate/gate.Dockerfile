# The shelf's gate (`just check-host`) in a Linux container. On the macOS host an endpoint
# scanner inspects every process start and file write, which makes the suite several times
# slower (a2kay measured 340 s on the host against 64 s here). Built and run by `just check`.
#
# Code is copied in, never bind-mounted: a bind mount brings the slow path back. The
# dependency layer is keyed on the manifests (every pyproject.toml + uv.lock) alone, so a
# code change rebuilds only the last two layers. .git comes along: `just guard` reads HEAD.

# make stays for blueprint's fallback tests (a consumer still on a Makefile is judged, then fails gate.runner);
# A C/C++ toolchain: anyembed's llama-cpp-python ships only an sdist and builds llama.cpp at sync.
# just itself arrives with the venv: `rust-just` is a dev dependency, run as `just` from /opt/venv/bin.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends git make build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    VIRTUAL_ENV=/opt/venv \
    UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/opt/venv/bin:$PATH \
    HYPOTHESIS_PROFILE=ci
RUN git config --global --add safe.directory '*' \
    && git config --global user.name "shelf gate" && git config --global user.email "gate@example.invalid" \
    && git config --global init.defaultBranch main

FROM base AS manifests
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /src
COPY . .
RUN mkdir /m && { find . -name pyproject.toml -not -path './.git/*'; echo uv.lock; } | tar -cf - -T - | tar -xf - -C /m

FROM base
WORKDIR /app
COPY --from=manifests /m/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-workspace
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync
