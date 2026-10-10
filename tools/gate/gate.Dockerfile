# The shelf's gate (`make check-host`) in a Linux container. On the macOS host an endpoint
# scanner inspects every process start and file write, which makes the suite several times
# slower (a2kay measured 340 s on the host against 64 s here). Built and run by `make check`.
#
# Code is copied in, never bind-mounted: a bind mount brings the slow path back. The
# dependency layer is keyed on the manifests (every pyproject.toml + uv.lock) alone, so a
# code change rebuilds only the last two layers. .git comes along: `make guard` reads HEAD.

FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends git make \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv
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
WORKDIR /src
COPY . .
RUN mkdir /m && { find . -name pyproject.toml -not -path './.git/*'; echo uv.lock; } | tar -cf - -T - | tar -xf - -C /m

FROM base
WORKDIR /app
COPY --from=manifests /m/ ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-install-workspace
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync
