"""The words of git's own diagnostics that this package classifies on: the one place they are written down.

Git has no machine-readable error codes for these, so a refusal is told apart by its message (``LC_ALL=C`` is set for
every child). Every pattern is a module constant, and ``tests/test_git_messages.py`` holds a real git sample for each
one, so a git release that rewords a message fails that test and not a user. Add a pattern here, never inline.
"""

from __future__ import annotations

import re
from typing import Final

# -- lock contention: another process holds a lock; retrying can succeed ---------------------------------
INDEX_LOCK: Final = re.compile(r"index\.lock")
#: git 2.53 words a fetch that loses the race to create a ref this way instead of naming the lock.
_FETCH_REF_EXISTS: Final = r"fetching ref \S+ failed: reference already exists"
REF_STALE: Final = re.compile(r"incorrect old value|is at \S+ but expected \S+")
REF_LOCK: Final = re.compile(rf"(?:cannot lock ref[^\n]*\.lock|Unable to create '[^'\n]*\.lock')[^\n]*File exists|{_FETCH_REF_EXISTS}")
REF_RACE: Final = re.compile(rf"cannot lock ref|unable to update local ref|Unable to create '[^']*\.lock'|{_FETCH_REF_EXISTS}")
#: Any lock message at all (a case-blind read of the whole output): the failure is worth retrying.
LOCKED: Final = re.compile(r"index\.lock|cannot lock ref|unable to create '|\.lock'", re.IGNORECASE)

# -- refusals with a type of their own -------------------------------------------------------------------
PINNED: Final = re.compile(r"already (?:checked out|used by worktree) at '?([^'\n]*)'?")
DIRTY_TREE: Final = re.compile(
    r"(?:local changes|untracked working tree files)[\s\S]*would be overwritten|would be overwritten by checkout"
)
BRANCH_EXISTS: Final = re.compile(r"(?:a branch named|a branch) '.+' already exists", re.IGNORECASE)
NO_BRANCH_NAMED: Final = re.compile(r"fatal: no branch named '.+'\.?", re.IGNORECASE)
TAG_EXISTS: Final = re.compile(r"tag '.+' already exists")
NOT_FAST_FORWARD: Final = re.compile(r"Not possible to fast-forward")

# -- a revision or a repository that is not there --------------------------------------------------------
MISSING_REVISION: Final = re.compile(r"fatal: (?:bad revision '.+'|Not a valid object name .+)")
AMBIGUOUS_REVISION: Final = re.compile(r"fatal: ambiguous argument '.+': unknown revision or path not in the working tree\.")
MERGE_NOT_MERGEABLE: Final = re.compile(r"merge: .+ - not something we can merge")
NOT_A_REPO_HERE: Final = re.compile(r"fatal: not a git repository \(or any of the parent directories\): \.git")
NOT_A_REPO_MOUNT: Final = re.compile(r"fatal: not a git repository \(or any parent up to mount point .+\)")
NOT_A_REPO_PATH: Final = re.compile(r"fatal: not a git repository:")
CANNOT_CHANGE_DIR: Final = re.compile(r"fatal: cannot change to '.+': No such file or directory")

# -- a commit that failed for a reason that is not a hook ------------------------------------------------
IDENTITY_UNKNOWN: Final = re.compile(r"tell me who you are|empty ident", re.IGNORECASE)
NOT_A_HOOK: Final = re.compile(
    r"gpg failed|unable to sign|failed to sign|identity unknown|tell me who you are|empty ident|index\.lock|cannot lock ref|"
    r"unmerged files|unresolved conflict|nothing to amend|failed to write commit object",
    re.IGNORECASE,
)

#: Every pattern above by name: what the sample test walks.
PATTERNS: Final[dict[str, re.Pattern[str]]] = {name: value for name, value in sorted(globals().items()) if isinstance(value, re.Pattern)}
