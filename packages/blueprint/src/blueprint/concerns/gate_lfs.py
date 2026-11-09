"""Gate lfs: owning domain checks and evidence."""

from __future__ import annotations

from blueprint.model import (
    Context,
    Finding,
    FixedBy,
    failing,
    not_applicable,
    not_set_up,
    passing,
)

# LFS: declared in .gitattributes, the pattern set is only the setup; git's own verdict on each blob is the proof.
_LFS_ATTR = "filter=lfs"
_NO_LFS = "the repo declares no LFS pattern (.gitattributes has no filter=lfs)"
_POINTER_HEAD, _POINTER_MAX = "version https://git-lfs.github.com/spec/v1", 1024
LFS_PACKAGE = (
    "install git-lfs with the system package manager (apt-get install git-lfs, brew install git-lfs), "
    "not through mise: its shim breaks `git clone`"
)
_LFS_INSTALL = "git lfs install --skip-repo (prek owns the hooks); then re-add each raw file: git rm --cached <path> && git add <path>"


def uses_lfs(ctx: Context) -> bool:
    return _LFS_ATTR in (ctx.read(".gitattributes") or "")


def _lfs_paths(ctx: Context, paths: list[str]) -> set[str]:
    """The paths an LFS pattern covers."""
    attrs = ctx.run("git", "check-attr", "filter", "--", *paths) if paths else None
    return {line.split(": ")[0] for line in (attrs.stdout if attrs else "").splitlines() if line.endswith(": filter: lfs")}


def _raw(ctx: Context, staged: dict[str, str], under: set[str]) -> list[str]:
    """LFS-pattern paths whose blob is not a pointer: a pointer is under 200 bytes and opens with its spec line."""
    raw: list[str] = []
    for path in sorted(under):
        size = (ctx.git("cat-file", "-s", staged[path]) or "0").strip()
        if int(size) > _POINTER_MAX or not (ctx.git("cat-file", "blob", staged[path]) or "").startswith(_POINTER_HEAD):
            raw.append(path)
    return raw


def lfs_binaries(ctx: Context) -> Finding:
    """Two misses: a binary no pattern covers (`git ls-files --eol` says `i/-text`), and a covered file stored raw.

    A covered file is `-text`, so `--eol` cannot judge it: its blob is read instead.
    """
    if not uses_lfs(ctx):
        return not_applicable(_NO_LFS)
    listed, staged_out = ctx.git("ls-files", "--eol", "-z"), ctx.git("ls-files", "-s", "-z")
    if listed is None or staged_out is None:
        return ctx.not_a_repository()
    staged = {e.split("\t", 1)[1]: e.split()[1] for e in staged_out.split("\0") if "\t" in e}
    binary = [e.split("\t", 1)[1] for e in listed.split("\0") if e.startswith("i/-text") and "\t" in e]
    under = _lfs_paths(ctx, sorted(staged))
    unlisted = [p for p in binary if p not in under]
    raw = _raw(ctx, staged, under)
    if not unlisted and not raw:
        return passing(f"{len(under)} files under LFS patterns, all pointers; no other binary in git")
    problems = [f"committed raw under an LFS pattern (that clone had no LFS filter): {', '.join(raw)}"] if raw else []
    problems += [f"binary with no LFS pattern: {', '.join(unlisted)}"] if unlisted else []
    return failing(
        "; ".join(problems),
        "add a `<pattern> filter=lfs diff=lfs merge=lfs -text` line for each unlisted type; " + _LFS_INSTALL,
    )


def lfs_installed(ctx: Context) -> Finding:
    """Without the filter, git stores the bytes and a fresh clone checks out pointers: the clone-local half of LFS."""
    if not uses_lfs(ctx):
        return not_applicable(_NO_LFS)
    if ctx.run("git", "lfs", "version") is None or not ctx.has("git-lfs"):
        return not_set_up(
            "git-lfs is not installed",
            LFS_PACKAGE + "; then " + _LFS_INSTALL,
        )
    if not (ctx.git("config", "--get", "filter.lfs.process") or ctx.git("config", "--get", "filter.lfs.clean")):
        return failing("the LFS filter is not configured: git lfs install was never run for this user", _LFS_INSTALL, FixedBy.AUTO)
    return passing("git-lfs installed and its filter configured")
