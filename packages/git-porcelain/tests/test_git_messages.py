"""Every pattern git-porcelain classifies a diagnostic by has a sample of what git printed, and matches it.

The samples are output of git 2.53.0 (``LC_ALL=C``), captured by hand for the failures a script can provoke; an entry
marked ``source`` is git's own message string where the fault (a full disk, a lost fetch race) cannot be provoked.
A git release that rewords a message turns its sample stale: re-capture it, then fix the pattern.
"""

from __future__ import annotations

import pytest

from git_porcelain.git_messages import PATTERNS

_SAMPLES: dict[str, list[str]] = {
    "INDEX_LOCK": ["fatal: Unable to create '/tmp/r/.git/index.lock': File exists.\n\nAnother git process seems to be running"],
    "REF_STALE": ["error: cannot lock ref 'refs/heads/qq': is at 7de61ba3 but expected 11111111"],
    "REF_LOCK": [
        "fatal: cannot lock ref 'refs/heads/zz': Unable to create '/tmp/r/.git/refs/heads/zz.lock': File exists.",
        "error: fetching ref refs/remotes/origin/main failed: reference already exists",  # source: git 2.53 fetch race
    ],
    "REF_RACE": [
        "fatal: cannot lock ref 'refs/heads/zz': Unable to create '/tmp/r/.git/refs/heads/zz.lock': File exists.",
        "error: unable to update local ref",  # source: builtin/fetch.c
    ],
    "LOCKED": [
        "fatal: Unable to create '/tmp/r/.git/index.lock': File exists.",
        "fatal: cannot lock ref 'refs/heads/zz': Unable to create '/tmp/r/.git/refs/heads/zz.lock': File exists.",
    ],
    "PINNED": ["fatal: 'other' is already used by worktree at '/private/tmp/gm/w'"],
    "DIRTY_TREE": [
        "error: Your local changes to the following files would be overwritten by checkout:\n\tf\nPlease commit your changes or stash them",
    ],
    "BRANCH_EXISTS": ["fatal: a branch named 'other' already exists"],
    "NO_BRANCH_NAMED": ["fatal: no branch named 'nonesuch'"],
    "TAG_EXISTS": ["fatal: tag 't' already exists"],
    "NOT_FAST_FORWARD": ["fatal: Not possible to fast-forward, aborting."],
    "MISSING_REVISION": ["fatal: bad revision 'nope'"],  # source: git log --end-of-options nope
    "AMBIGUOUS_REVISION": ["fatal: ambiguous argument 'nope': unknown revision or path not in the working tree."],
    "MERGE_NOT_MERGEABLE": ["merge: nope - not something we can merge"],
    "NOT_A_REPO_HERE": ["fatal: not a git repository (or any of the parent directories): .git"],
    "NOT_A_REPO_MOUNT": [
        "fatal: not a git repository (or any parent up to mount point /)"
    ],  # source: Linux, GIT_DISCOVERY_ACROSS_FILESYSTEM unset
    "NOT_A_REPO_PATH": ["fatal: not a git repository: '/tmp/x'"],  # source: GIT_DIR pointing at a non-repository
    "CANNOT_CHANGE_DIR": ["fatal: cannot change to '/nonexistent': No such file or directory"],
    "IDENTITY_UNKNOWN": ["Author identity unknown\n\n*** Please tell me who you are."],
    "NOT_A_HOOK": [
        "error: gpg failed to sign the data:\n(no gpg output)",
        "Author identity unknown\n\n*** Please tell me who you are.",
        "fatal: Unable to create '/tmp/r/.git/index.lock': File exists.",
        "error: Committing is not possible because you have unmerged files.",
        "fatal: You have nothing to amend.",
        "fatal: failed to write commit object",  # source: builtin/commit.c
    ],
}


def test_every_pattern_has_a_sample_and_every_sample_a_pattern() -> None:
    assert set(PATTERNS) == set(_SAMPLES), "a pattern in git_messages.py needs a real git sample here (and no sample outlives its pattern)"


@pytest.mark.parametrize(("name", "sample"), [(name, sample) for name, samples in _SAMPLES.items() for sample in samples])
def test_a_pattern_matches_what_git_printed(name: str, sample: str) -> None:
    assert PATTERNS[name].search(sample), f"{name} no longer matches its sample"
