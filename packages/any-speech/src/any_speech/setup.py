"""Build FluidAudio's command line at the commit Reco builds and install it where `find_fluidaudio` looks."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING, Protocol

import app_dirs
from child_env import NotFound, find
from stream_proc import run_inherited

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

APP = "any-speech"
FLUIDAUDIO_REPO = "https://github.com/FluidInference/FluidAudio"
FLUIDAUDIO_COMMIT = "0b1f46289fe27d95b5e66ad8be46e64f5ee02ae7"  # the checkout Reco builds and our measurements used
BINARY = "fluidaudiocli"
COMMIT_SUFFIX = ".commit"
_STEP_TIMEOUT = 3600.0  # one git or swift step; a release build of FluidAudio is the long one


class SetupError(RuntimeError):
    """The build could not be made; the message says what to fix."""


class StepRunner(Protocol):
    def __call__(self, args: Sequence[str | Path], *, cwd: Path | None = None) -> None: ...


def installed_binary(env: Mapping[str, str], home: Path) -> Path:
    """Under the state dir, because the binary is rebuilt by `setup` and must survive a cache clean."""
    return app_dirs.state_dir(APP, env=env, home=home) / "bin" / BINARY


def _run(args: Sequence[str | Path], *, cwd: Path | None = None) -> None:
    argv = [str(a) for a in args]
    exit_ = run_inherited(argv, cwd=cwd, timeout=_STEP_TIMEOUT)  # output goes to the terminal: a build is watched
    if exit_ != 0:
        raise subprocess.CalledProcessError(exit_, argv)


def install_fluidaudio(
    env: Mapping[str, str],
    home: Path,
    *,
    run: StepRunner = _run,
    work: Path | None = None,
) -> Path:
    try:
        swift, git = find("swift", env).path, find("git", env).path
    except NotFound as error:
        message = f"`{error.name}` was not found: install Xcode (or its command line tools) and run `any-speech setup fluidaudio` again"
        raise SetupError(message) from error
    checkout = work or app_dirs.cache_dir(APP, env=env, home=home) / "fluidaudio-src"
    try:
        if not (checkout / ".git").exists():
            run([git, "clone", FLUIDAUDIO_REPO, checkout])
        run([git, "fetch", "origin", FLUIDAUDIO_COMMIT], cwd=checkout)
        run([git, "checkout", "--detach", FLUIDAUDIO_COMMIT], cwd=checkout)
        run([swift, "build", "-c", "release", "--product", BINARY], cwd=checkout)
    except (subprocess.CalledProcessError, OSError) as error:
        message = f"building FluidAudio failed: {error}"
        raise SetupError(message) from error
    built = checkout / ".build" / "release" / BINARY
    target = installed_binary(env, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, target)
    target.with_name(BINARY + COMMIT_SUFFIX).write_text(FLUIDAUDIO_COMMIT, encoding="utf-8")
    return target
