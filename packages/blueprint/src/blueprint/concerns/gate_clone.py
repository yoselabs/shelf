"""Gate clone: owning domain checks and evidence."""

from __future__ import annotations

import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint import gate_graph
from blueprint.concerns.gate_lfs import LFS_PACKAGE, uses_lfs
from blueprint.model import (
    Context,
    Finding,
    FixedBy,
    Verdict,
    failing,
    not_checked,
    not_set_up,
    passing,
)

if TYPE_CHECKING:
    import subprocess


# The runner's own trailer (`make: *** [check] Error 2`, "error: Recipe `lint` failed on line 9 ...") names no cause.
_RUNNER_LINE = re.compile(r"^(?:g?make(\[\d+\])?: |error: Recipe `)")


def _cause(done: subprocess.CompletedProcess[str]) -> str:
    """The last line of the failing run's output that the runner did not write itself; stderr first, it carries the error."""
    for stream in (done.stderr, done.stdout):
        lines = [line.strip() for line in stream.splitlines() if line.strip() and not _RUNNER_LINE.match(line.strip())]
        if lines:
            return lines[-1]
    return "no output"


def _judge_clone(done: subprocess.CompletedProcess[str] | None, took: int, budget: object, ctx: Context, word: str = "just") -> Finding:
    if done is None:
        return failing(f"`{word} check` in a fresh clone did not finish within an hour", "find the step that hangs")
    if done.returncode != 0:
        return failing(f"`{word} check` fails in a fresh clone ({took}s): {_cause(done)}", "make the gate pass from a clean checkout")
    if not isinstance(budget, int):
        return not_set_up(
            f"fresh-clone gate passed in {took}s; no budget recorded",
            f"record `clean-clone-seconds = {took * 2}` under [settings] in docs/blueprint/blueprint.toml",
            FixedBy.AUTO,
        )
    if took > budget:
        # The load is context for the owner's call (a busy machine reads as a slow gate), never a threshold.
        return failing(
            f"fresh-clone gate took {took}s, budget {budget}s, this machine's {_load_average(ctx)}",
            "speed the gate up, or raise the budget with the owner",
            FixedBy.OWNER,
        )
    return passing(f"fresh-clone gate passed in {took}s (budget {budget}s)")


# `uptime` on macOS ("load averages: 2.31 2.05 1.90") and Linux ("load average: 0.08, 0.03, 0.05"): the 1-minute first.
_LOAD_AVERAGE = re.compile(r"load averages?:\s*([\d.]+)")


def _load_average(ctx: Context) -> str:
    """This machine's 1-minute load average, or that it could not be read: context for an over-budget gate."""
    done = ctx.run("uptime", timeout=30)
    found = _LOAD_AVERAGE.search(done.stdout) if done is not None and done.returncode == 0 else None
    return f"load average {found.group(1)}" if found else "load average unavailable (`uptime` did not answer)"


# What a fresh clone needs before its gate can run, in order: until `mise trust` every mise shim refuses (uv
# included), and a beads repo's database is not in git, it is pulled from refs/dolt/data (a2kay: shelf-45k, 8q7).
_FRESH_CLONE_STEPS = (
    ("mise.toml", ("mise", "trust", "--yes", ".")),
    ("mise.toml", ("mise", "install", "--locked")),
    # The stack's sync once, before the gate's parallel steps each start building the same environment at once.
    ("uv.lock", ("uv", "sync", "--locked")),
    (".beads/config.yaml", ("bd", "bootstrap", "--yes")),
)


_OTHER_TRANSPORT = tuple(
    {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{to}.insteadOf", "GIT_CONFIG_VALUE_0": frm}
    for to, frm in (("git@github.com:", "https://github.com/"), ("https://github.com/", "ssh://git@github.com/"))
)


def _fresh_clone_steps(ctx: Context, clone: Path) -> Finding | None:
    """Run each step the clone's files call for; the first that fails is the finding."""
    env = {**ctx.env, "MISE_IGNORED_CONFIG_PATHS": str(Path.home() / ".config" / "mise"), "BD_DISABLE_METRICS": "1"}
    for marker, argv in _FRESH_CLONE_STEPS:
        if not (clone / marker).is_file():
            continue
        done = ctx.run(*argv, cwd=clone, timeout=600, env=env)
        if argv[0] == "bd" and done is not None and done.returncode != 0:
            # The committed sync.remote may name the transport this machine lacks (https on an SSH-only box, ssh in CI).
            for rewrite in _OTHER_TRANSPORT:
                done = ctx.run(*argv, cwd=clone, timeout=600, env={**env, **rewrite})
                if done is not None and done.returncode == 0:
                    break
        if done is None or done.returncode != 0:
            why = "not installed or timed out" if done is None else _cause(done)
            return failing(
                f"fresh-clone step `{' '.join(argv)}` failed: {why}", "make the documented after-clone steps work on a new clone"
            )
    return None


def clean_clone(ctx: Context) -> Finding:
    """Clone HEAD into a temp dir and run `just check` (a Makefile repo: `make check`) there, timed.

    When HEAD fails and the working tree holds uncommitted changes, the same run on a snapshot of the working tree tells
    "commit to verify" (mid-remediation, a2kay: shelf-83g) from a real failure; the row passes only on HEAD.
    """
    if ctx.git("rev-parse", "HEAD") is None:
        return not_checked("no commit to clone")
    word = "make" if gate_graph.has_makefile_only(ctx) else "just"
    budget = ctx.settings.get("clean-clone-seconds")
    with tempfile.TemporaryDirectory(prefix="blueprint-clone-") as tmp:
        # GIT_LFS_SKIP_SMUDGE: a git-lfs on PATH that fails (a mise shim in an untrusted checkout) must not fail the clone itself.
        clone = ctx.run("git", "clone", "--quiet", str(ctx.repo), tmp, timeout=300, env={**ctx.env, "GIT_LFS_SKIP_SMUDGE": "1"})
        if clone is None or clone.returncode != 0:
            return not_checked("could not clone the repository")
        judged = (_pull_lfs(ctx, Path(tmp)) if uses_lfs(ctx) else None) or _gate_in(ctx, Path(tmp), word, budget)
    uncommitted = [
        line[3:] for line in (ctx.git("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=all") or "").splitlines()
    ]
    if judged.verdict is not Verdict.FAILING or not uncommitted:
        return judged
    with tempfile.TemporaryDirectory(prefix="blueprint-snapshot-") as tmp:
        if not _snapshot(ctx, Path(tmp)):
            return judged
        if _gate_in(ctx, Path(tmp), word, budget).verdict is Verdict.FAILING:
            return judged
    named = ", ".join(uncommitted[:5]) + (f" and {len(uncommitted) - 5} more" if len(uncommitted) > 5 else "")
    return not_checked(
        f"{judged.evidence}; the working tree passes in a snapshot clone: commit to verify (uncommitted: {named})",
        "commit the changes on the owner's yes and re-run the audit; a file the gate needs but nobody commits belongs in the gate",
        FixedBy.OWNER,
    )


def _pull_lfs(ctx: Context, clone: Path) -> Finding | None:
    """The clone skipped the LFS smudge; fetch the real files so the gate does not run on pointers."""
    version = ctx.run("git", "lfs", "version")
    if version is None or version.returncode != 0:
        return not_checked("the repo uses LFS and git-lfs is not installed: the fresh clone holds pointers, not files", LFS_PACKAGE)
    done = ctx.run("git", "lfs", "pull", cwd=clone, timeout=1800, env={**ctx.env, "GIT_LFS_SKIP_SMUDGE": "1"})
    if done is None or done.returncode != 0:
        why = "timed out" if done is None else _cause(done)
        return not_checked(
            f"the repo uses LFS and `git lfs pull` in the fresh clone failed: {why}", "make `git lfs pull` work from a new clone"
        )
    return None


def _gate_in(ctx: Context, folder: Path, word: str, budget: object) -> Finding:
    """The after-clone steps, then the gate, in `folder`, timed against the recorded budget."""
    start = time.monotonic()
    if (failed := _fresh_clone_steps(ctx, folder)) is not None:
        return failed
    done = ctx.run(gate_graph.just_command(ctx) if word == "just" else word, "check", cwd=folder, timeout=3600)
    return _judge_clone(done, round(time.monotonic() - start), budget, ctx, word)


def _snapshot(ctx: Context, folder: Path) -> bool:
    """A one-commit repo of the working tree as it is: tracked and untracked files git does not ignore."""
    listed = ctx.git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if listed is None:
        return False
    for rel in filter(None, listed.split("\0")):
        source = ctx.path(rel)
        if source.is_file():
            target = folder / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    steps = (
        ("init", "-q"),
        ("add", "-A"),
        ("-c", "user.email=blueprint@invalid", "-c", "user.name=blueprint", "commit", "-qm", "snapshot"),
    )
    return all((done := ctx.run("git", *args, cwd=folder, timeout=300)) is not None and done.returncode == 0 for args in steps)
