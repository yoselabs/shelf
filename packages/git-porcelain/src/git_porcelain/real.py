"""``RealGit``: the :class:`~git_porcelain.api.Git` protocol over the git binary.

It reuses the package's runner (``run_git``: no prompts, no inherited ``GIT_DIR``, fail loud). The answers
that cannot change while the process works on one checkout (``common_dir``, ``toplevel``, the remote URL,
config values, the current branch) are memoized: a driver that asks for them dozens of times a run costs
one git process each. Every write this object makes clears the memo; a change made behind its back (another
process, a hand edit) needs :meth:`RealGit.invalidate`. ``memoize=False`` turns the memo off.
"""

from __future__ import annotations

import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypeVar, cast

from git_porcelain.api import FileStat, Git, ResetMode, Worktree
from git_porcelain.errors import GitError
from git_porcelain.history import RemoteError, classify_remote_failure
from git_porcelain.porcelain import StatusEntry, _run, git_dir, run_git, status, unmerged_paths

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

__all__ = ["RealGit"]

# Another process fetching into the same repository at the same moment: the ref is then where it should be,
# the fetch only lost the lock (task-loop measured 150 of 180 simultaneous fetches failing so).
_REF_RACE: Final = re.compile(r"incorrect old value|cannot lock ref|unable to update local ref|Unable to create '[^']*\.lock'")
_FETCH_TRIES: Final = 5
_UNBORN: Final = "0" * 40
_T = TypeVar("_T")


def _lines(text: str, sep: str = "\n") -> list[str]:
    return [line for line in text.split(sep) if line]


class RealGit:
    """The git binary behind the :class:`~git_porcelain.api.Git` protocol, bound to one checkout."""

    def __init__(
        self,
        path: Path,
        *,
        env: Mapping[str, str] | None = None,
        memoize: bool = True,
        sleep: Callable[[float], None] = time.sleep,
        _memo: dict[tuple[Path, str, str], object] | None = None,
    ) -> None:
        self._path = path
        self._env = dict(env or {})
        self._memoize = memoize
        self._sleep = sleep
        self._memo: dict[tuple[Path, str, str], object] = {} if _memo is None else _memo

    @property
    def path(self) -> Path:
        return self._path

    def at(self, path: Path) -> Git:
        return RealGit(path, env=self._env, memoize=self._memoize, sleep=self._sleep, _memo=self._memo)

    def invalidate(self) -> None:
        self._memo.clear()

    # -- plumbing ------------------------------------------------------------------------------------
    def _git(self, *args: str, check: bool = True, stdin: str | None = None) -> str:
        return run_git(self._path, *args, check=check, env=self._env, stdin=stdin)

    def _rc(self, *args: str) -> int:
        return _run(self._path, args, self._env, None).returncode

    def _write(self, *args: str, stdin: str | None = None) -> None:
        try:
            self._git(*args, stdin=stdin)
        finally:
            self.invalidate()

    def _cached(self, name: str, arg: str, compute: Callable[[], _T]) -> _T:
        key = (self._path, name, arg)
        if self._memoize and key in self._memo:
            return cast("_T", self._memo[key])
        value = compute()
        if self._memoize:
            self._memo[key] = value
        return value

    # -- reads ---------------------------------------------------------------------------------------
    def head(self) -> str | None:
        return self.resolve("HEAD")

    def resolve(self, rev: str) -> str | None:
        return self._git("rev-parse", "--verify", "-q", f"{rev}^{{commit}}", check=False).strip() or None

    def branch(self) -> str | None:
        return self._cached("branch", "", lambda: self._git("symbolic-ref", "--short", "-q", "HEAD", check=False).strip() or None)

    def common_dir(self) -> Path:
        return self._cached("common_dir", "", lambda: Path(self._git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()))

    def toplevel(self) -> Path:
        return self._cached("toplevel", "", lambda: Path(self._git("rev-parse", "--show-toplevel").strip()))

    def is_inside_work_tree(self) -> bool:
        return self._cached("inside", "", lambda: self._git("rev-parse", "--is-inside-work-tree", check=False).strip() == "true")

    def remote_url(self, remote: str = "origin") -> str | None:
        return self._cached("remote_url", remote, lambda: self._git("remote", "get-url", remote, check=False).strip() or None)

    def config_get(self, key: str) -> str | None:
        def read() -> str | None:
            out = self._git("config", "--get", key, check=False)
            return out.rstrip("\n") if out else None

        return self._cached("config", key, read)

    def tree_hash(self) -> str:
        with tempfile.TemporaryDirectory() as folder:
            env = {**self._env, "GIT_INDEX_FILE": str(Path(folder) / "index")}
            if self.head() is not None:
                run_git(self._path, "read-tree", "HEAD", env=env)
            run_git(self._path, "add", "-A", env=env)
            return run_git(self._path, "write-tree", env=env).strip()

    def status(self) -> list[StatusEntry]:
        return status(self._path, env=self._env)

    def unmerged(self) -> list[str]:
        return unmerged_paths(self._path, env=self._env)

    def rebase_in_progress(self) -> bool:
        found = git_dir(self._path)
        return found is not None and any((found / name).is_dir() for name in ("rebase-merge", "rebase-apply"))

    def merge_base(self, a: str, b: str) -> str | None:
        return self._git("merge-base", a, b, check=False).strip() or None

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return self._rc("merge-base", "--is-ancestor", ancestor, descendant) == 0

    def rev_list_count(self, rev_range: str) -> int:
        return int(self._git("rev-list", "--count", rev_range).strip())

    def log_subjects(self, rev_range: str, *, limit: int | None = None) -> list[str]:
        cap = [] if limit is None else ["-n", str(limit)]
        return _lines(self._git("log", "--format=%s", *cap, rev_range))

    @staticmethod
    def _scope(exclude: Sequence[str]) -> list[str]:
        return ["--", ".", *(f":(exclude,literal){p}" for p in exclude)] if exclude else []

    def diff(self, a: str, b: str, *, exclude: Sequence[str] = ()) -> str:
        return self._git("diff", "--no-color", "--no-ext-diff", "--no-renames", a, b, *self._scope(exclude))

    def diff_names(self, a: str, b: str) -> list[str]:
        return sorted(_lines(self._git("diff", "--name-only", "-z", "--no-renames", a, b), "\0"))

    def diff_stat(self, a: str, b: str, *, exclude: Sequence[str] = ()) -> list[FileStat]:
        out = self._git("diff", "--numstat", "--no-renames", "-z", a, b, *self._scope(exclude))
        stats: list[FileStat] = []
        for record in _lines(out, "\0"):
            added, deleted, name = record.split("\t", 2)
            stats.append(FileStat(name, 0 if added == "-" else int(added), 0 if deleted == "-" else int(deleted)))
        return sorted(stats, key=lambda s: s.path)

    def show(self, rev: str, path: str) -> str | None:
        done = _run(self._path, ("show", f"{rev}:{path}"), self._env, None)
        return done.stdout if done.returncode == 0 else None

    def ls_tree(self, rev: str) -> list[str]:
        return sorted(_lines(self._git("ls-tree", "-r", "--name-only", "-z", rev), "\0"))

    def ls_files(self) -> list[str]:
        return sorted(set(_lines(self._git("ls-files", "-z"), "\0")))

    def grep_files(self, term: str) -> list[str]:
        done = _run(self._path, ("grep", "-w", "-I", "-l", "-z", "-F", "-e", term), self._env, None)
        if done.returncode not in (0, 1):
            msg = f"git grep exited {done.returncode}: {done.stderr.strip()[:300]}"
            raise GitError(msg)
        return sorted(_lines(done.stdout, "\0"))

    def ignored(self, paths: Sequence[str], rules: Sequence[str]) -> set[str]:
        if not paths:
            return set()
        with tempfile.TemporaryDirectory() as folder:
            rules_file = Path(folder) / "rules"
            rules_file.write_text("\n".join(rules) + "\n", encoding="utf-8")
            args = ("-c", f"core.excludesFile={rules_file}", "check-ignore", "--no-index", "--stdin", "-z")
            done = _run(self._path, args, self._env, None, "\0".join(paths) + "\0")
        if done.returncode not in (0, 1):
            msg = f"git check-ignore exited {done.returncode}: {done.stderr.strip()[:300]}"
            raise GitError(msg)
        return set(_lines(done.stdout, "\0"))

    def worktree_list(self) -> list[Worktree]:
        found: list[Worktree] = []
        for block in self._git("worktree", "list", "--porcelain").split("\n\n"):
            fields = dict(line.partition(" ")[::2] for line in block.splitlines() if line)
            if "worktree" not in fields:
                continue
            sha = fields.get("HEAD", _UNBORN)
            ref = fields.get("branch")
            branch = ref.removeprefix("refs/heads/") if ref else None
            found.append(Worktree(Path(fields["worktree"]), None if sha == _UNBORN else sha, branch))
        return found

    # -- writes --------------------------------------------------------------------------------------
    def add(self, paths: Sequence[str] | None = None) -> None:
        if paths is None:
            self._write("add", "-A")
        elif paths:
            self._write("--literal-pathspecs", "add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul", stdin="\0".join(paths))

    def commit(self, message: str, *, allow_empty: bool = False) -> str:
        self._write("commit", "-q", "--no-verify", *(["--allow-empty"] if allow_empty else []), "-m", message)
        return self.head() or ""

    def checkout(self, branch: str) -> None:
        self._write("checkout", "-q", branch, "--")

    def checkout_new(self, branch: str, start: str | None = None, *, reset: bool = False) -> None:
        self._write("checkout", "-q", "-B" if reset else "-b", branch, *([start] if start else []))

    def detach(self, rev: str = "HEAD") -> None:
        self._write("checkout", "-q", "--detach", rev)

    def branch_rename(self, old: str, new: str) -> None:
        self._write("branch", "-m", old, new)

    def reset(self, rev: str, mode: ResetMode) -> None:
        self._write("reset", "-q", f"--{mode}", rev)

    def rebase(self, onto: str) -> bool:
        try:
            self._write("rebase", "-q", onto)
        except GitError:
            if self.rebase_in_progress():
                return False
            raise
        return True

    def rebase_abort(self) -> None:
        self._write("rebase", "--abort")

    def clean(self, keep: Sequence[str] = ()) -> None:
        self._write("clean", "-fdq", *(arg for pattern in keep for arg in ("-e", pattern)))

    def worktree_add(self, path: Path, rev: str) -> Git:
        self._write("worktree", "add", "-q", "--detach", str(path), rev)
        return self.at(path)

    def worktree_remove(self, path: Path, *, force: bool = False) -> None:
        self._write("worktree", "remove", *(["--force"] if force else []), str(path))

    def worktree_prune(self) -> None:
        self._write("worktree", "prune")

    def fetch(self, remote: str = "origin") -> None:
        for attempt in range(_FETCH_TRIES):
            try:
                self._run_remote("fetch", "--quiet", remote)
            except RemoteError as exc:
                if attempt == _FETCH_TRIES - 1 or not _REF_RACE.search(str(exc)):
                    raise
                self._sleep(0.1 * (attempt + 1))
            else:
                return

    def push(self, src: str, dst: str, remote: str = "origin") -> None:
        self._run_remote("push", "--porcelain", remote, f"{src}:refs/heads/{dst}")

    def _run_remote(self, *args: str) -> None:
        try:
            self._write(*args)
        except GitError as exc:
            raise RemoteError(str(exc), reason="offline" if exc.retryable else classify_remote_failure(str(exc))) from exc
