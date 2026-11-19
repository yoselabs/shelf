"""Build FluidAudio's command line at the commit Reco builds and install it where `find_fluidaudio` looks."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING, Protocol

import app_dirs

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

APP = "any-speech"
FLUIDAUDIO_REPO = "https://github.com/FluidInference/FluidAudio"
FLUIDAUDIO_COMMIT = "0b1f46289fe27d95b5e66ad8be46e64f5ee02ae7"  # the checkout Reco builds and our measurements used
BINARY = "fluidaudiocli"
COMMIT_SUFFIX = ".commit"


class SetupError(RuntimeError):
    """The build could not be made; the message says what to fix."""


class Run(Protocol):
    def __call__(self, args: Sequence[str | Path], *, cwd: Path | None = None) -> None: ...


def installed_binary(env: Mapping[str, str], home: Path) -> Path:
    """Under the state dir, because the binary is rebuilt by `setup` and must survive a cache clean."""
    return app_dirs.state_dir(APP, env=env, home=home) / "bin" / BINARY


def _run(args: Sequence[str | Path], *, cwd: Path | None = None) -> None:
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def install_fluidaudio(
    env: Mapping[str, str],
    home: Path,
    *,
    run: Run = _run,
    which: Callable[[str], str | None] = shutil.which,
    work: Path | None = None,
) -> Path:
    if which("swift") is None:
        message = "`swift` was not found: install Xcode (or its command line tools) and run `any-speech setup fluidaudio` again"
        raise SetupError(message)
    checkout = work or app_dirs.cache_dir(APP, env=env, home=home) / "fluidaudio-src"
    try:
        if not (checkout / ".git").exists():
            run(["git", "clone", FLUIDAUDIO_REPO, checkout])
        run(["git", "fetch", "origin", FLUIDAUDIO_COMMIT], cwd=checkout)
        run(["git", "checkout", "--detach", FLUIDAUDIO_COMMIT], cwd=checkout)
        run(["swift", "build", "-c", "release", "--product", BINARY], cwd=checkout)
    except (subprocess.CalledProcessError, OSError) as error:
        message = f"building FluidAudio failed: {error}"
        raise SetupError(message) from error
    built = checkout / ".build" / "release" / BINARY
    target = installed_binary(env, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, target)
    target.with_name(BINARY + COMMIT_SUFFIX).write_text(FLUIDAUDIO_COMMIT, encoding="utf-8")
    return target
