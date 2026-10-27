@contract
Feature: One Repo and Worktree, real or fake
  Every intent operation a driver such as task-loop takes on a checkout behaves the same on the git binary
  (RealRepo) and in memory (FakeRepo). These scenarios run against both; @real_only names a gap of the fake.

  # -- identity ----------------------------------------------------------------------------------------
  Scenario: A repository says where it is, and names itself the same from every worktree
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    When "r" calls identity()
    Then the result's root is "<root>/r"
    And the result's common_dir is "<root>/r/.git"
    And the result's origin_url is None
    When "r" remembers identity().key as "key"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And "w" calls identity()
    Then the result's key is "<mem:key>"
    And the result's root is "<root>/r"

  Scenario: The origin url is read from the remote
    Given a repository "r"
    And an origin "o"
    And "r" has the origin "o" as remote "origin"
    When "r" calls identity()
    Then the result's origin_url is "<root>/o.git"

  # -- health ------------------------------------------------------------------------------------------
  Scenario: A plain checkout is healthy
    Given a repository "r"
    When "r" calls health()
    Then the result's ok is True
    And the result's problem is None
    And the result's worktree_config is False

  Scenario: A stray core.worktree is found, and says which file to fix
    Given a repository "r"
    And a folder "elsewhere"
    When "r" config "core.worktree" becomes "<root>/elsewhere"
    And "r" calls health()
    Then the result's ok is False
    And the result's problem is "worktree_redirected"
    And the result's set_in is "<root>/r/.git/config"

  Scenario: A bare marking is found
    Given a repository "r"
    When "r" config "core.bare" becomes "true"
    And "r" calls health()
    Then the result's problem is "bare"
    And the result's set_in is "<root>/r/.git/config"

  Scenario: A checkout whose top level is another folder is found
    Given a repository "r"
    And "inner" is the folder "inner" inside "r"
    When "inner" calls health()
    Then the result's problem is "toplevel_mismatch"
    And the result's set_in is None

  Scenario: Health is never remembered
    Given a repository "r"
    And a folder "elsewhere"
    When "r" calls health()
    Then the result's ok is True
    When "r" config "extensions.worktreeConfig" becomes "true"
    And "r" config "core.worktree" becomes "<root>/elsewhere"
    And "r" calls health()
    Then the result's problem is "worktree_redirected"
    And the result's worktree_config is True

  # -- snapshot ----------------------------------------------------------------------------------------
  Scenario: A clean checkout snapshots to its committed tree
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", dir/b.txt="b\n"
    When "r" calls snapshot("HEAD")
    Then the result's tree equals its head_tree
    And the result's branch is "main"
    And the result's head is "<head:r>"
    And the result's base is "<head:r>"
    And the result's base_tip is "<head:r>"

  Scenario: Untracked files count, ignored ones do not, and the real index is left alone
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", .gitignore="*.log\n"
    And "r" remembers snapshot("HEAD").tree as "clean"
    When "r" writes b.txt="b\n", skip.log="s\n"
    And "r" calls snapshot("HEAD")
    Then the result's tree is not "<mem:clean>"
    And the result's head_tree is "<mem:clean>"
    When "r" calls dirty()
    Then the result's tracked is []
    And the result's untracked is ["b.txt"]

  Scenario: Equal content gives an equal tree in another checkout
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", dir/b.txt="b\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    When "w" writes new.txt="new\n"
    And "r" writes new.txt="new\n"
    And "r" remembers snapshot("HEAD").tree as "mine"
    And "w" calls snapshot("HEAD")
    Then the result's tree is "<mem:mine>"

  Scenario: The base is where the branch left the base ref, the base tip is where that ref is now
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "fork"
    When "r" commits "mine" with b.txt="b\n"
    And "r" remembers its head as "mine"
    And the origin "o" advances "main" with c.txt="c\n"
    And "r" calls sync()
    And "r" calls snapshot("origin/main")
    Then the result's head is "<mem:mine>"
    And the result's base is "<mem:fork>"
    And the result's base_tip is not "<mem:fork>"

  Scenario: A repository with no commit snapshots to the tree of its files
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And a repository "r"
    And "r" has the origin "o" as remote "origin"
    And "r" calls sync()
    When "r" writes z.txt="z\n"
    And "r" calls snapshot("origin/main")
    Then the result's head is None
    And the result's head_tree is None
    And the result's branch is "main"
    And the result's base equals its base_tip

  Scenario: Two same-size edits within one clock tick give two different trees
    Given a repository "r"
    And "r" commits "base" with a.txt="aaaa\n"
    And "r" writes a.txt="bbbb\n"
    And "r" remembers snapshot("HEAD").tree as "first"
    When "r" edits "a.txt" to "cccc\n" within the same clock tick
    And "r" calls snapshot("HEAD")
    Then the result's tree is not "<mem:first>"

  Scenario: A base that names nothing is an infrastructure failure
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n"
    When "r" tries snapshot("origin/nowhere")
    Then the call raises GitUnavailable

  # -- diff --------------------------------------------------------------------------------------------
  Scenario: A diff between two commits lists the changes and carries the patch
    Given a repository "r"
    And "r" commits "base" with a.txt="one\ntwo\nthree\n", b.txt="keep\n"
    And "r" remembers its head as "base"
    And "r" commits "change" with a.txt="one\n2\nthree\nfour\n", d.txt="new\n"
    When "r" calls diff("<mem:base>", "HEAD")
    Then the result's changes are ["a.txt M +2 -1", "d.txt A +1 -0"]
    And the result's truncated is False
    When "r" calls diff("<mem:base>", "HEAD", exclude=["d.txt"])
    Then the result's changes are ["a.txt M +2 -1"]
    And the result's patch is "diff --git a/a.txt b/a.txt\nindex <blob:one\ntwo\nthree\n>..<blob:one\n2\nthree\nfour\n> 100644\n--- a/a.txt\n+++ b/a.txt\n@@ -1,3 +1,4 @@\n one\n-two\n+2\n three\n+four\n"

  Scenario: A diff names the function a hunk sits in, and marks new and deleted files
    Given a repository "r"
    And "r" commits "base" with code.py="def f():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 5\n    return a\n", gone.txt="bye\n"
    And "r" remembers its head as "base"
    And "r" removes "gone.txt"
    And "r" commits "change" with code.py="def f():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 50\n    return a\n", fresh.txt="hi\n"
    When "r" calls diff("<mem:base>", "HEAD")
    Then the result's changes are ["code.py M +1 -1", "fresh.txt A +1 -0", "gone.txt D +0 -1"]
    And the result's patch is "diff --git a/code.py b/code.py\nindex <blob:def f():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 5\n    return a\n>..<blob:def f():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 50\n    return a\n> 100644\n--- a/code.py\n+++ b/code.py\n@@ -3,5 +3,5 @@ def f():\n     b = 2\n     c = 3\n     d = 4\n-    e = 5\n+    e = 50\n     return a\ndiff --git a/fresh.txt b/fresh.txt\nnew file mode 100644\nindex 0000000..<blob:hi\n>\n--- /dev/null\n+++ b/fresh.txt\n@@ -0,0 +1 @@\n+hi\ndiff --git a/gone.txt b/gone.txt\ndeleted file mode 100644\nindex <blob:bye\n>..0000000\n--- a/gone.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-bye\n"

  Scenario: A patch longer than the cap is cut and says so
    Given a repository "r"
    And "r" commits "base" with a.txt="one\n"
    And "r" remembers its head as "base"
    And "r" commits "change" with a.txt="one\ntwo\nthree\n"
    When "r" calls diff("<mem:base>", "HEAD", cap=10)
    Then the result's truncated is True
    And the result's patch is "diff --git"
    And the result's changes are ["a.txt M +2 -0"]

  Scenario: No change is an empty diff, not an error
    Given a repository "r"
    And "r" commits "base" with a.txt="one\n"
    When "r" calls diff("HEAD", "HEAD")
    Then the result's changes are []
    And the result's patch is ""
    And the result's truncated is False

  Scenario: A snapshot tree can be diffed against a commit, untracked files included
    Given a repository "r"
    And "r" commits "base" with a.txt="one\n"
    And "r" writes new.txt="fresh\n"
    And "r" remembers snapshot("HEAD").tree as "work"
    When "r" calls diff("HEAD", "<mem:work>")
    Then the result's changes are ["new.txt A +1 -0"]

  # -- dirty -------------------------------------------------------------------------------------------
  Scenario: Tracked and untracked changes come from one call, ignored files stay out
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", b.txt="b\n", c.txt="c\n", .gitignore="*.log\n"
    When "r" writes a.txt="a changed\n", e.txt="e\n", noise.log="ignored\n"
    And "r" removes "b.txt"
    And "r" calls dirty()
    Then the result's tracked is ["a.txt", "b.txt"]
    And the result's untracked is ["e.txt"]
    And the result's base_ignored is []
    And the result's ignored is []

  Scenario: Paths with spaces and non-ASCII letters come back as written
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n"
    When "r" writes "my file.txt"="x\n", café/ü.txt="y\n"
    And "r" calls dirty()
    Then the result's untracked is ["café/ü.txt", "my file.txt"]

  Scenario: The base's own ignore rules mark the untracked files it would ignore, nested ones too
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And the origin "o" advances "main" with .gitignore="*.tmp\n", sub/.gitignore="out/\n"
    And "r" calls sync()
    When "r" writes cache.tmp="t\n", sub/out/x.bin="x\n", sub/keep.txt="k\n"
    And "r" calls dirty("origin/main")
    Then the result's untracked is ["cache.tmp", "sub/keep.txt", "sub/out/x.bin"]
    And the result's base_ignored is ["cache.tmp", "sub/out/x.bin"]

  Scenario: Ignored files are listed only below the prefixes asked for
    Given a repository "r"
    And "r" commits "base" with .gitignore="*.log\n", a.txt="a\n"
    When "r" writes build/a.log="1\n", build/keep.txt="2\n", other/b.log="3\n"
    And "r" calls dirty(ignored_under=["build"])
    Then the result's ignored is ["build/a.log"]
    And the result's untracked is ["build/keep.txt"]
    When "r" calls dirty()
    Then the result's ignored is []

  # -- record ------------------------------------------------------------------------------------------
  Scenario: Own paths leave out what the base would ignore, all paths take everything
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And the origin "o" advances "main" with .gitignore="*.tmp\n"
    And "r" calls sync()
    When "r" writes a.txt="2\n", cache.tmp="t\n", new.txt="n\n"
    And "r" calls record("work", base="origin/main")
    Then the result is a Recorded
    When "r" calls dirty()
    Then the result's untracked is ["cache.tmp"]
    When "r" calls record("rest", paths="all")
    Then the result is a Recorded
    When "r" calls dirty()
    Then the result's untracked is []
    And the result's tracked is []

  Scenario: Nothing to commit is a result, and an empty commit can be asked for
    Given a repository "r"
    And "r" commits "first" with a.txt="1\n"
    When "r" calls record("again")
    Then the result is a NothingToRecord
    When "r" calls record("on purpose", allow_empty=True)
    Then the result is a Recorded

  Scenario: Amend folds into the last commit and keeps its message when none is given
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" commits "two" with a.txt="2\n"
    When "r" writes a.txt="3\n"
    And "r" calls record("", mode="amend")
    Then the result is a Recorded
    When "r" calls history(["HEAD"])
    Then the subject of each result entry is ["two", "one"]
    When "r" writes a.txt="4\n"
    And "r" calls record("two, fixed", mode="amend")
    And "r" calls history(["HEAD"])
    Then the subject of each result entry is ["two, fixed", "one"]

  Scenario: Squash-to folds the commits above a point into one
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" remembers its head as "fork"
    And "r" commits "two" with b.txt="2\n"
    And "r" commits "three" with c.txt="3\n"
    When "r" calls record("squashed", mode="squash_to", squash_to="<mem:fork>")
    Then the result is a Recorded
    When "r" calls history(["HEAD"])
    Then the subject of each result entry is ["squashed", "one"]
    And the file "c.txt" of "r" holds "3\n"

  Scenario: A pre-commit hook refuses only when hooks are asked for
    Given a repository "r"
    And "r" commits "base" with a.txt="1\n"
    And "r" has a pre-commit hook that refuses
    When "r" writes a.txt="2\n"
    And "r" calls record("guarded", hooks=True)
    Then the result is a HookRejected
    When "r" calls record("quick")
    Then the result is a Recorded

  Scenario: A held index lock is an infrastructure failure that may be retried
    Given a repository "r"
    And "r" commits "base" with a.txt="1\n"
    And "r" holds an index lock
    When "r" writes a.txt="2\n"
    And "r" tries record("blocked")
    Then the call raises GitUnavailable
    And the failure may be retried

  @real_only
  Scenario: A configured identity commits where git has none (the fake has no authors)
    Given the machine has no git identity
    And the repositories commit as "Injected Author"
    And a repository "r"
    When "r" writes a.txt="1\n"
    And "r" calls record("by the program")
    Then the result is a Recorded
    And the author of the last commit of "r" is "Injected Author"

  @real_only
  Scenario: No identity anywhere says how to fix it (the fake has no authors)
    Given the machine has no git identity
    And a repository "r"
    When "r" writes a.txt="1\n"
    And "r" tries record("nobody")
    Then the call raises GitUnavailable
    And the failure hint is "set user.name and user.email"

  # -- take_branch -------------------------------------------------------------------------------------
  Scenario: Resume takes an existing branch as it is, and makes a missing one at the base
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    When "r" calls take_branch("task/x", "HEAD", mode="resume")
    Then the result is a BranchTaken
    And the result's created is True
    When "r" commits "two" with b.txt="2\n"
    And "r" remembers its head as "two"
    And "r" calls take_branch("main", "HEAD", mode="resume")
    Then the result's created is False
    And the file "b.txt" of "r" is absent
    When "r" calls take_branch("task/x", "main", mode="resume")
    Then the result's created is False
    And the result's head is "<mem:two>"
    And the result's kept_aside is None
    And the file "b.txt" of "r" holds "2\n"

  Scenario: Fresh keeps the old work aside under the name given, and starts again at the base
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" commits "work" with b.txt="2\n"
    And "r" remembers its head as "work"
    When "r" calls take_branch("task/x", "main", mode="fresh", keep_aside_as="task/x-stale")
    Then the result's created is True
    And the result's head is "<mem:base>"
    And the result's kept_aside is "task/x-stale"
    And the file "b.txt" of "r" is absent
    When "r" calls branches("task/")
    Then the first item of each result entry is ["task/x", "task/x-stale"]
    And the second item of each result entry is ["<mem:base>", "<mem:work>"]

  Scenario: Fresh over a branch with no work beyond the base keeps nothing aside
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    When "r" calls take_branch("task/x", "main", mode="fresh", keep_aside_as="task/x-stale")
    Then the result's kept_aside is None
    When "r" calls branches("task/")
    Then the first item of each result entry is ["task/x"]

  Scenario: Restart drops the old tip and starts at the base
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" commits "work" with b.txt="2\n"
    When "r" calls take_branch("task/x", "main", mode="restart")
    Then the result's head is "<mem:base>"
    And the result's kept_aside is None
    And the result's created is False

  Scenario: A branch another worktree holds is not taken
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" adds a worktree "w" at "main" as "w"
    When "w" calls take_branch("task/x", "main", mode="fresh")
    Then the result is a BranchHeld
    And the result's holders.0.path is "<root>/r"
    And the result's holders.0.branch is "task/x"

  Scenario: Clean-keep deletes untracked files except the patterns it is given
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    When "r" writes keep.out="k\n", junk.txt="j\n"
    And "r" calls take_branch("task/x", "HEAD", mode="fresh", clean_keep=["*.out"])
    And "r" calls dirty()
    Then the result's untracked is ["keep.out"]

  # -- release_branch and park -------------------------------------------------------------------------
  Scenario: A clean holder is removed
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "main" as "w"
    And "w" calls take_branch("task/x", "main", mode="fresh")
    When "r" calls release_branch("<root>/w")
    Then the result is a Released
    And the result's how is "removed"
    When "r" calls worktrees()
    Then the result has 1 entries

  Scenario: A dirty holder is detached where it stands
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "main" as "w"
    And "w" calls take_branch("task/x", "main", mode="fresh")
    And "w" writes junk.txt="j\n"
    When "r" calls release_branch("<root>/w")
    Then the result's how is "detached"
    When "r" calls worktrees()
    Then the result has 2 entries
    And the branch of each result entry is ["main", None]

  Scenario: The main checkout is never released
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "main" as "w"
    When "w" calls release_branch("<root>/r")
    Then the result is a StillHeld

  Scenario: Parking detaches at the base and keeps the branch
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" commits "work" with b.txt="2\n"
    When "r" calls park("main")
    Then the result is "<mem:base>"
    When "r" calls snapshot("main")
    Then the result's branch is None
    And the result's head is "<mem:base>"
    When "r" calls branches("task/")
    Then the first item of each result entry is ["task/x"]

  # -- rebase ------------------------------------------------------------------------------------------
  Scenario: A branch level with its base is up to date
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    When "r" calls rebase_onto("origin/main")
    Then the result is a UpToDate

  Scenario: A moved base is rebased onto, and the old and new heads are reported
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with c.txt="c\n"
    And "r" remembers its head as "mine"
    And the origin "o" advances "main" with d.txt="d\n"
    And "r" calls sync()
    When "r" calls rebase_onto("origin/main")
    Then the result is a Rebased
    And the result's old_head is "<mem:mine>"
    And the result's new_head is not "<mem:mine>"
    And the result's squashed is False
    And the file "d.txt" of "r" holds "d\n"
    And the file "c.txt" of "r" holds "c\n"

  Scenario: Wip commits are squashed first when a message is given
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "wip one" with c.txt="c\n"
    And "r" commits "wip two" with e.txt="e\n"
    And "r" remembers its head as "mine"
    And the origin "o" advances "main" with d.txt="d\n"
    And "r" calls sync()
    When "r" calls rebase_onto("origin/main", squash_message="task (bead-1)")
    Then the result is a Rebased
    And the result's squashed is True
    And the result's old_head is "<mem:mine>"
    When "r" calls history(["HEAD"], not_on=["origin/main"])
    Then the subject of each result entry is ["task (bead-1)"]
    And the file "e.txt" of "r" holds "e\n"

  Scenario: A conflict leaves the rebase paused with the files named
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a.txt="mine\n"
    And "r" remembers its head as "mine"
    And the origin "o" advances "main" with a.txt="theirs\n"
    And "r" calls sync()
    When "r" calls rebase_onto("origin/main")
    Then the result is a Conflict
    And the result's files are ["a.txt"]
    And the result's old_head is "<mem:mine>"
    And the file "a.txt" of "r" has conflict markers
    When "r" tries rebase_onto("origin/main")
    Then the call raises ValueError

  Scenario: A tree with tracked changes is not rebased
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And the origin "o" advances "main" with d.txt="d\n"
    And "r" calls sync()
    When "r" writes a.txt="edited\n"
    And "r" tries rebase_onto("origin/main")
    Then the call raises ValueError

  # -- finish_rebase -----------------------------------------------------------------------------------
  Scenario: Continuing with markers left reports the files and stays paused
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a.txt="mine\n"
    And the origin "o" advances "main" with a.txt="theirs\n"
    And "r" calls sync()
    And "r" calls rebase_onto("origin/main")
    When "r" calls finish_rebase("continue")
    Then the result is a Conflict
    And the result's files are ["a.txt"]
    And the file "a.txt" of "r" has conflict markers

  Scenario: Continuing after the markers are gone finishes the rebase
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a.txt="mine\n"
    And "r" remembers its head as "mine"
    And the origin "o" advances "main" with a.txt="theirs\n"
    And "r" calls sync()
    And "r" calls rebase_onto("origin/main")
    When "r" writes a.txt="resolved\n"
    And "r" calls finish_rebase("continue")
    Then the result is a Rebased
    And the result's old_head is "<mem:mine>"
    And the file "a.txt" of "r" holds "resolved\n"
    When "r" calls history(["HEAD"], not_on=["origin/main"])
    Then the subject of each result entry is ["mine"]
    When "r" calls dirty()
    Then the result's tracked is []

  Scenario: Aborting returns to where the rebase began
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a.txt="mine\n"
    And "r" remembers its head as "mine"
    And the origin "o" advances "main" with a.txt="theirs\n"
    And "r" calls sync()
    And "r" calls rebase_onto("origin/main")
    When "r" calls finish_rebase("abort")
    Then the result is a Aborted
    And the result's head is "<mem:mine>"
    And the file "a.txt" of "r" holds "mine\n"

  Scenario: Aborting a squashed rebase can restore the work as it was before the squash
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "wip one" with a.txt="mine\n"
    And "r" commits "wip two" with b.txt="b\n"
    And "r" remembers its head as "before"
    And the origin "o" advances "main" with a.txt="theirs\n"
    And "r" calls sync()
    And "r" calls rebase_onto("origin/main", squash_message="squashed")
    When "r" calls finish_rebase("abort", restore_to="<mem:before>")
    Then the result's head is "<mem:before>"
    When "r" calls history(["HEAD"], not_on=["origin/main"])
    Then the subject of each result entry is ["wip two", "wip one"]

  Scenario: With nothing paused, finishing is a no-op
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    When "r" calls finish_rebase("abort")
    Then the result is a Aborted
    And the result's head is "<head:r>"
    When "r" calls finish_rebase("continue")
    Then the result is a Rebased
    And the result's new_head equals its old_head

  # -- push --------------------------------------------------------------------------------------------
  Scenario: A push of new work lands it on the origin's branch
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "work" with f.txt="f\n"
    When "r" calls push("main")
    Then the result is a Pushed
    And the result's sha is "<head:r>"
    When "r" calls relate("HEAD", "origin/main")
    Then the result's ahead is 0
    And the result's behind is 0

  Scenario: A push behind the origin is rejected
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "work" with f.txt="f\n"
    And the origin "o" advances "main" with g.txt="g\n"
    When "r" calls push("main")
    Then the result is a Rejected

  Scenario: A push to an origin that cannot be reached is transient
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "work" with f.txt="f\n"
    And the origin "o" is offline
    When "r" calls push("main")
    Then the result is a Transient

  Scenario: A pre-push hook that refuses is not a network error
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" has a pre-push hook that refuses
    And "r" commits "work" with f.txt="f\n"
    When "r" calls push("main")
    Then the result is a HookRejected

  Scenario: The hook sees the environment it is given
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" has a pre-push hook that needs X=1
    And "r" commits "work" with f.txt="f\n"
    When "r" calls push("main")
    Then the result is a HookRejected
    When "r" calls push("main", hook_env={"X": "1"})
    Then the result is a Pushed

  # -- landed ------------------------------------------------------------------------------------------
  Scenario: A commit with the title suffix is landed once it is on the base
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "task (bead-1)" with f.txt="f\n"
    When "r" calls landed("origin/main", "(bead-1)")
    Then the result is None
    When "r" calls push("main")
    And "r" calls landed("origin/main", "(bead-1)")
    Then the result is "<head:r>"
    When "r" calls landed("origin/main", "(bead-2)")
    Then the result is None

  # -- sync --------------------------------------------------------------------------------------------
  Scenario: Sync brings the origin's branches
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And the origin "o" advances "main" with b.txt="b\n"
    When "r" calls sync()
    Then the result is a Synced
    When "r" calls relate("HEAD", "origin/main")
    Then the result's behind is 1

  Scenario: Sync says when the origin cannot be reached
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And the origin "o" is offline
    When "r" calls sync()
    Then the result is a Offline

  @real_only
  Scenario: A fetch that loses a ref lock to a competing fetch tries again (the fake has no locks)
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And the origin "o" advances "main" with b.txt="b\n"
    And a competing fetch holds the lock on "origin/main" until the first retry
    When "r" calls sync()
    Then the result is a Synced
    And the fetch rested 1 time

  # -- relate, history, branches, tree -----------------------------------------------------------------
  Scenario: Relate gives the merge base and both counts in one look
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "fork"
    And "r" commits "mine one" with b.txt="1\n"
    And "r" commits "mine two" with b.txt="2\n"
    And the origin "o" advances "main" with c.txt="c\n"
    And "r" calls sync()
    When "r" calls relate("HEAD", "origin/main")
    Then the result's merge_base is "<mem:fork>"
    And the result's ahead is 2
    And the result's behind is 1
    When "r" calls relate("origin/main", "HEAD")
    Then the result's ahead is 1
    And the result's behind is 2
    When "r" tries relate("HEAD", "nonsense")
    Then the call raises GitUnavailable

  Scenario: History lists commits newest first, from some revisions and not on others
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "one\n\nthe body" with b.txt="1\n"
    And "r" commits "two" with b.txt="2\n"
    When "r" calls history(["HEAD"], not_on=["origin/main"])
    Then the subject of each result entry is ["two", "one"]
    And the body of each result entry is ["", "the body"]
    When "r" calls history(["HEAD"], limit=1)
    Then the subject of each result entry is ["two"]
    And the upstream of each result entry is [None]

  Scenario: History marks the commits whose patch is already on the base
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with f.txt="f\n"
    And "r" commits "other" with g.txt="g\n"
    And the origin "o" advances "main" with f.txt="f\n"
    And "r" calls sync()
    When "r" calls history(["HEAD"], not_on=["origin/main~1"], patch_equivalent_to="origin/main")
    Then the subject of each result entry is ["other", "mine"]
    And the upstream of each result entry is [False, True]

  Scenario: Branches are listed by prefix with their tips
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/a", "main", mode="resume")
    And "r" calls take_branch("task/b", "main", mode="resume")
    And "r" calls take_branch("wip/c", "main", mode="resume")
    When "r" calls branches("task/")
    Then the first item of each result entry is ["task/a", "task/b"]
    When "r" calls branches()
    Then the first item of each result entry is ["main", "task/a", "task/b", "wip/c"]

  Scenario: A tree lists its files and reads them lazily
    Given a repository "r"
    And "r" commits "one" with a.txt="v1\n", dir/b.txt="b\n"
    And "r" remembers its head as "base"
    And "r" commits "two" with a.txt="v2\n"
    When "r" calls tree("<mem:base>")
    Then the tree lists ["a.txt", "dir/b.txt"]
    And the tree reads "a.txt" as "v1\n"
    And the tree reads "absent.txt" as nothing
    When "r" calls tree("HEAD")
    Then the tree reads "a.txt" as "v2\n"
    When "r" calls tree("nonsense")
    Then the result is None

  Scenario: A snapshot's tree id is a tree too, untracked files included
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" writes new.txt="n\n"
    And "r" remembers snapshot("HEAD").tree as "work"
    When "r" calls tree("<mem:work>")
    Then the tree lists ["a.txt", "new.txt"]
    And the tree reads "new.txt" as "n\n"

  # -- worktrees ---------------------------------------------------------------------------------------
  Scenario: Worktrees are listed with the main one first, dirty only when asked
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And "r" writes junk.txt="j\n"
    When "r" calls worktrees()
    Then the result has 2 entries
    And the path of each result entry is ["<root>/r", "<root>/w"]
    And the branch of each result entry is ["main", None]
    And the is_main of each result entry is [True, False]
    And the dirty of each result entry is [None, None]
    When "r" calls worktrees(with_dirty=True)
    Then the dirty of each result entry is [True, False]
    And the head of each result entry is ["<head:r>", "<head:r>"]

  Scenario: A clean worktree is dropped, a dirty one needs force
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And "w" writes junk.txt="j\n"
    When "r" tries drop_worktree("<root>/w")
    Then the call raises GitUnavailable
    When "r" calls drop_worktree("<root>/w", force=True)
    And "r" calls worktrees()
    Then the result has 1 entries

  Scenario: A worktree whose folder is gone is forgotten
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And the folder of "w" is deleted behind git's back
    When "r" calls drop_worktree("<root>/w")
    And "r" calls worktrees()
    Then the result has 1 entries

  Scenario: Local excludes keep paths out of status, and are written once
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    When "r" calls exclude_locally([".task/", ".slots/"])
    And "r" calls exclude_locally([".task/"])
    And "r" writes .task/x="x\n", .slots/y="y\n", z.txt="z\n"
    And "r" calls dirty()
    Then the result's untracked is ["z.txt"]

  @real_only
  Scenario: The exclude file gets each line once (the fake keeps a list)
    Given a repository "r"
    When "r" calls exclude_locally([".task/", ".slots/"])
    And "r" calls exclude_locally([".task/", ".more/"])
    Then the file ".git/info/exclude" of "r" holds ".task/\n.slots/\n.more/\n"

  # -- infrastructure ----------------------------------------------------------------------------------
  Scenario: A folder that is no repository is an infrastructure failure
    Given "plain" is the plain folder
    When "plain" tries dirty()
    Then the call raises GitUnavailable
    When "plain" tries snapshot("HEAD")
    Then the call raises GitUnavailable

  @real_only
  Scenario: A missing git binary is an infrastructure failure (the fake runs no binary)
    Given a repository "r"
    When git is not on the PATH
    And "r" tries dirty()
    Then the call raises GitUnavailable

  # -- grep --------------------------------------------------------------------------------------------
  Scenario: Tracked files are searched for a whole word
    Given a repository "r"
    And "r" commits "one" with a.txt="uses ripgrep here\n", b.txt="ripgrepper\n"
    When "r" writes c.txt="ripgrep too\n"
    And "r" calls grep_tracked("ripgrep")
    Then the result is ["a.txt"]
