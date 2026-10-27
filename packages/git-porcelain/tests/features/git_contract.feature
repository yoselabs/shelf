@contract
Feature: One Git, real or fake
  Every operation a driver such as task-loop makes on a checkout behaves the same on the git binary
  (RealGit) and in memory (FakeGit). These scenarios run against both.

  Scenario: A new repository is unborn, and says where it is
    Given a repository "r"
    When "r" calls head()
    Then the result is None
    When "r" calls branch()
    Then the result is "main"
    When "r" calls toplevel()
    Then the result is "<root>/r"
    When "r" calls common_dir()
    Then the result is "<root>/r/.git"
    When "r" calls is_inside_work_tree()
    Then the result is True

  Scenario: A folder outside any repository is not a work tree
    Given "plain" is the plain folder
    When "plain" calls is_inside_work_tree()
    Then the result is False
    When "plain" tries toplevel()
    Then the call fails

  Scenario: Config and remote answer None until set
    Given a repository "r"
    When "r" calls config_get("demo.key")
    Then the result is None
    When "r" calls remote_url("origin")
    Then the result is None
    Given "r" config "demo.key" is "value one"
    And an origin "o"
    And "r" has the origin "o" as remote "origin"
    When "r" calls config_get("demo.key")
    Then the result is "value one"
    When "r" calls remote_url()
    Then the result is "<root>/o.git"

  Scenario: Staging, committing and reading history back
    Given a repository "r"
    When "r" writes a.txt="one\n"
    And "r" calls status()
    Then the result is ["?? a.txt"]
    When "r" calls add()
    And "r" calls status()
    Then the result is ["A  a.txt"]
    When "r" calls commit("first")
    Then the result is "<head:r>"
    When "r" calls status()
    Then the result is []
    When "r" commits "second" with a.txt="one\ntwo\n"
    And "r" calls log_subjects("HEAD")
    Then the result is ["second", "first"]
    When "r" calls log_subjects("HEAD", limit=1)
    Then the result is ["second"]
    When "r" calls resolve("HEAD~1")
    Then the result looks like a sha
    When "r" calls resolve("nonsense")
    Then the result is None

  Scenario: A commit with nothing staged fails unless it may be empty
    Given a repository "r"
    And "r" commits "first" with a.txt="one\n"
    When "r" tries commit("again")
    Then the call fails
    When "r" calls commit("empty on purpose", allow_empty=True)
    Then the result looks like a sha
    When "r" calls rev_list_count("HEAD")
    Then the result is 2

  Scenario: Status codes for every kind of change
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", b.txt="b\n", c.txt="c\n", d.txt="d\n", .gitignore="*.log\n"
    When "r" writes a.txt="a changed\n"
    And "r" writes b.txt="b changed\n"
    And "r" calls add(["b.txt"])
    And "r" writes b.txt="b changed again\n"
    And "r" removes "c.txt"
    And "r" writes e.txt="e\n"
    And "r" writes noise.log="ignored\n"
    And "r" calls status()
    Then the result is [" M a.txt", "MM b.txt", " D c.txt", "?? e.txt"]

  Scenario: A staged rename is one entry that remembers where it came from
    Given a repository "r"
    And "r" commits "base" with old.txt="same content\n"
    When "r" removes "old.txt"
    And "r" writes new.txt="same content\n"
    And "r" calls add()
    And "r" calls status()
    Then the result is ["R  new.txt <- old.txt"]

  Scenario: Add takes literal paths, deletions and folders, and refuses what it cannot find
    Given a repository "r"
    And "r" commits "base" with keep.txt="k\n", gone.txt="g\n"
    When "r" removes "gone.txt"
    And "r" writes a.txt="a\n", b.txt="b\n", dir/x.txt="x\n", dir/y.txt="y\n"
    And "r" calls add(["a.txt", "gone.txt"])
    And "r" calls status()
    Then the result is ["A  a.txt", "D  gone.txt", "?? b.txt", "?? dir/x.txt", "?? dir/y.txt"]
    When "r" calls add(["dir"])
    And "r" calls ls_files()
    Then the result is ["a.txt", "dir/x.txt", "dir/y.txt", "keep.txt"]
    When "r" tries add(["missing.txt"])
    Then the call fails

  Scenario: Add everything leaves ignored files out
    Given a repository "r"
    And "r" commits "base" with .gitignore="*.log\nbuild/\n"
    When "r" writes a.txt="a\n", noise.log="n\n", build/out.bin="o\n"
    And "r" calls add()
    And "r" calls ls_files()
    Then the result is [".gitignore", "a.txt"]
    When "r" tries add(["noise.log"])
    Then the call fails

  Scenario: The tree hash is the tree a commit would make, and touches nothing
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", .gitignore="*.log\n"
    When "r" writes b.txt="b\n", skip.log="s\n"
    And "r" removes "a.txt"
    And "r" calls tree_hash()
    Then the result looks like a sha
    When "r" calls diff_names("HEAD", "<tree:r>")
    Then the result is ["a.txt", "b.txt"]
    When "r" calls status()
    Then the result is [" D a.txt", "?? b.txt"]
    When "r" calls ls_files()
    Then the result is [".gitignore", "a.txt"]
    When "r" calls add()
    And "r" commits "second" with c.txt="c\n"
    And "r" calls ls_tree("HEAD")
    Then the result is [".gitignore", "b.txt", "c.txt"]

  Scenario: Equal content has an equal tree hash in another checkout
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", dir/b.txt="b\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And "w" writes new.txt="new\n"
    And "r" writes new.txt="new\n"
    Then the tree hash of "r" equals the tree hash of "w"

  Scenario: Diff text, names and statistics
    Given a repository "r"
    And "r" commits "base" with a.txt="one\ntwo\nthree\n", b.txt="keep\n"
    When "r" remembers its head as "base"
    And "r" commits "change" with a.txt="one\n2\nthree\nfour\n", d.txt="new\n"
    And "r" calls diff_names("<mem:base>", "HEAD")
    Then the result is ["a.txt", "d.txt"]
    When "r" calls diff_stat("<mem:base>", "HEAD")
    Then the result is ["a.txt +2 -1", "d.txt +1 -0"]
    When "r" calls diff_stat("<mem:base>", "HEAD", exclude=["d.txt"])
    Then the result is ["a.txt +2 -1"]
    When "r" calls diff("<mem:base>", "HEAD", exclude=["d.txt"])
    Then the result is "diff --git a/a.txt b/a.txt\nindex <blob:one\ntwo\nthree\n>..<blob:one\n2\nthree\nfour\n> 100644\n--- a/a.txt\n+++ b/a.txt\n@@ -1,3 +1,4 @@\n one\n-two\n+2\n three\n+four\n"

  Scenario: A diff names the function a hunk sits in, and marks new and deleted files
    Given a repository "r"
    And "r" commits "base" with code.py="def f():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 5\n    return a\n", gone.txt="bye\n"
    When "r" remembers its head as "base"
    And "r" removes "gone.txt"
    And "r" commits "change" with code.py="def f():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 50\n    return a\n", fresh.txt="hi\n"
    And "r" calls diff("<mem:base>", "HEAD")
    Then the result is "diff --git a/code.py b/code.py\nindex <blob:def f():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 5\n    return a\n>..<blob:def f():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 50\n    return a\n> 100644\n--- a/code.py\n+++ b/code.py\n@@ -3,5 +3,5 @@ def f():\n     b = 2\n     c = 3\n     d = 4\n-    e = 5\n+    e = 50\n     return a\ndiff --git a/fresh.txt b/fresh.txt\nnew file mode 100644\nindex 0000000..<blob:hi\n>\n--- /dev/null\n+++ b/fresh.txt\n@@ -0,0 +1 @@\n+hi\ndiff --git a/gone.txt b/gone.txt\ndeleted file mode 100644\nindex <blob:bye\n>..0000000\n--- a/gone.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-bye\n"

  Scenario: Reading a file, a tree and the index at a revision
    Given a repository "r"
    And "r" commits "base" with a.txt="v1\n", dir/b.txt="b\n"
    When "r" remembers its head as "base"
    And "r" commits "second" with a.txt="v2\n"
    And "r" calls show("<mem:base>", "a.txt")
    Then the result is "v1\n"
    When "r" calls show("HEAD", "a.txt")
    Then the result is "v2\n"
    When "r" calls show("HEAD", "absent.txt")
    Then the result is None
    When "r" calls show("nonsense", "a.txt")
    Then the result is None
    When "r" calls ls_tree("HEAD")
    Then the result is ["a.txt", "dir/b.txt"]
    When "r" calls ls_files()
    Then the result is ["a.txt", "dir/b.txt"]
    When "r" tries ls_tree("nonsense")
    Then the call fails

  Scenario: Ranges, ancestry and the merge base
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" remembers its head as "one"
    And "r" calls checkout_new("side")
    And "r" commits "side two" with s.txt="s\n"
    And "r" commits "side three" with s.txt="s3\n"
    And "r" calls checkout("main")
    And "r" commits "main two" with m.txt="m\n"
    When "r" calls rev_list_count("main..side")
    Then the result is 2
    When "r" calls rev_list_count("side..main")
    Then the result is 1
    When "r" calls log_subjects("main..side")
    Then the result is ["side three", "side two"]
    When "r" calls merge_base("main", "side")
    Then the result is "<mem:one>"
    When "r" calls is_ancestor("<mem:one>", "side")
    Then the result is True
    When "r" calls is_ancestor("side", "main")
    Then the result is False
    When "r" tries rev_list_count("nonsense..main")
    Then the call fails

  Scenario: Switching branches, renaming, detaching and resetting
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" remembers its head as "one"
    When "r" calls checkout_new("feature")
    And "r" commits "two" with a.txt="2\n"
    And "r" calls branch()
    Then the result is "feature"
    When "r" calls checkout("main")
    Then the file "a.txt" of "r" holds "1\n"
    When "r" calls branch_rename("feature", "renamed")
    And "r" calls checkout("renamed")
    Then the file "a.txt" of "r" holds "2\n"
    When "r" calls detach("main")
    And "r" calls branch()
    Then the result is None
    When "r" calls head()
    Then the result is "<mem:one>"
    When "r" calls checkout("renamed")
    And "r" calls reset("<mem:one>", "soft")
    And "r" calls status()
    Then the result is ["M  a.txt"]
    When "r" calls reset("<mem:one>", "hard")
    And "r" calls status()
    Then the result is []
    And the file "a.txt" of "r" holds "1\n"
    When "r" calls checkout_new("renamed", "<mem:one>", reset=True)
    And "r" calls branch()
    Then the result is "renamed"
    When "r" tries checkout("nowhere")
    Then the call fails
    When "r" tries checkout_new("main")
    Then the call fails

  Scenario: Switching carries edits that do not collide and refuses to lose ones that do
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n", b.txt="1\n"
    And "r" calls checkout_new("feature")
    And "r" commits "two" with a.txt="2\n"
    And "r" calls checkout("main")
    When "r" writes b.txt="local\n"
    And "r" calls checkout("feature")
    And "r" calls status()
    Then the result is [" M b.txt"]
    When "r" calls checkout("main")
    And "r" calls reset("HEAD", "hard")
    And "r" writes a.txt="mine\n"
    And "r" tries checkout("feature")
    Then the call fails
    And the file "a.txt" of "r" holds "mine\n"

  Scenario: Linked worktrees share the repository and each hold their own branch
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    When "r" adds a worktree "w1" at "HEAD" as "w1"
    And "w1" calls branch()
    Then the result is None
    When "w1" calls toplevel()
    Then the result is "<root>/w1"
    When "w1" calls common_dir()
    Then the result is "<root>/r/.git"
    When "r" calls worktree_list()
    Then the result is ["<root>/r main", "<root>/w1 (detached)"]
    When "w1" calls checkout_new("task")
    And "r" tries checkout("task")
    Then the call fails
    When "r" tries checkout_new("task", reset=True)
    Then the call fails
    When "w1" writes x.txt="x\n"
    And "r" tries worktree_remove("<root>/w1")
    Then the call fails
    When "r" calls worktree_remove("<root>/w1", force=True)
    And "r" calls worktree_list()
    Then the result is ["<root>/r main"]

  Scenario: A worktree whose folder vanished is listed until it is pruned
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w2" at "HEAD" as "w2"
    When the folder of "w2" is deleted behind git's back
    And "r" calls worktree_list()
    Then the result is ["<root>/r main", "<root>/w2 (detached)"]
    When "r" calls worktree_prune()
    And "r" calls worktree_list()
    Then the result is ["<root>/r main"]

  Scenario: A rebase replays the branch onto a base that moved
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", b.txt="b\n"
    And "r" calls checkout_new("task")
    And "r" commits "task work" with t.txt="t\n"
    And "r" calls checkout("main")
    And "r" commits "main moves" with m.txt="m\n"
    And "r" calls checkout("task")
    When "r" calls rev_list_count("HEAD..main")
    Then the result is 1
    When "r" calls rebase("main")
    Then the result is True
    When "r" calls rev_list_count("HEAD..main")
    Then the result is 0
    When "r" calls log_subjects("HEAD", limit=2)
    Then the result is ["task work", "main moves"]
    When "r" calls ls_files()
    Then the result is ["a.txt", "b.txt", "m.txt", "t.txt"]
    When "r" calls branch()
    Then the result is "task"
    When "r" calls rebase_in_progress()
    Then the result is False

  Scenario: A rebase onto an ancestor does nothing, onto a descendant fast-forwards
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n"
    And "r" remembers its head as "base"
    And "r" calls checkout_new("task")
    And "r" calls checkout("main")
    And "r" commits "main moves" with m.txt="m\n"
    When "r" calls checkout("task")
    And "r" calls rebase("main")
    Then the result is True
    When "r" calls head()
    Then the result is "<head:r>"
    And the file "m.txt" of "r" holds "m\n"
    When "r" calls rev_list_count("main..HEAD")
    Then the result is 0
    When "r" calls rebase("<mem:base>")
    Then the result is True
    When "r" calls log_subjects("HEAD", limit=1)
    Then the result is ["main moves"]

  Scenario: Edits in different lines of one file merge in a rebase
    Given a repository "r"
    And "r" commits "base" with f.txt="1\n2\n3\n4\n5\n6\n7\n8\n9\n"
    And "r" calls checkout_new("task")
    And "r" commits "task edit" with f.txt="1\ntwo\n3\n4\n5\n6\n7\n8\n9\n"
    And "r" calls checkout("main")
    And "r" commits "main edit" with f.txt="1\n2\n3\n4\n5\n6\n7\neight\n9\n"
    And "r" calls checkout("task")
    When "r" calls rebase("main")
    Then the result is True
    And the file "f.txt" of "r" holds "1\ntwo\n3\n4\n5\n6\n7\neight\n9\n"

  Scenario: A rebase that conflicts stops, names the file, and can be abandoned
    Given a repository "r"
    And "r" commits "base" with f.txt="x\n"
    And "r" calls checkout_new("task")
    And "r" commits "task edit" with f.txt="task\n"
    And "r" remembers its head as "task"
    And "r" calls checkout("main")
    And "r" commits "main edit" with f.txt="main\n"
    And "r" calls checkout("task")
    When "r" calls rebase("main")
    Then the result is False
    When "r" calls rebase_in_progress()
    Then the result is True
    When "r" calls unmerged()
    Then the result is ["f.txt"]
    When "r" calls status()
    Then the result is ["UU f.txt"]
    And the file "f.txt" of "r" has conflict markers
    When "r" calls branch()
    Then the result is None
    When "r" calls rebase_abort()
    And "r" calls rebase_in_progress()
    Then the result is False
    When "r" calls head()
    Then the result is "<mem:task>"
    And the file "f.txt" of "r" holds "task\n"
    When "r" calls branch()
    Then the result is "task"
    When "r" calls status()
    Then the result is []

  Scenario: A rebase refuses a tree with uncommitted edits
    Given a repository "r"
    And "r" commits "base" with f.txt="x\n"
    And "r" calls checkout_new("task")
    And "r" commits "task" with t.txt="t\n"
    And "r" calls checkout("main")
    And "r" commits "main" with m.txt="m\n"
    And "r" calls checkout("task")
    When "r" writes t.txt="edited\n"
    And "r" tries rebase("main")
    Then the call fails
    And the file "t.txt" of "r" holds "edited\n"

  Scenario: Clean removes untracked files and spares ignored and kept ones
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", .gitignore="*.log\n"
    When "r" writes a.txt="a edited\n", junk.txt="j\n", keep.txt="k\n", noise.log="n\n", sub/deep.txt="d\n"
    And "r" calls clean(["keep.txt"])
    And "r" calls status()
    Then the result is [" M a.txt", "?? keep.txt"]
    And the file "noise.log" of "r" holds "n\n"
    And the file "junk.txt" of "r" is absent
    And the file "sub/deep.txt" of "r" is absent

  Scenario: Grep finds whole words in tracked files only
    Given a repository "r"
    And "r" commits "base" with a.txt="we use ruff here\n", b.txt="rufffoo\n", c.txt="nothing\n"
    When "r" writes u.txt="ruff\n"
    And "r" calls grep_files("ruff")
    Then the result is ["a.txt"]
    When "r" calls grep_files("absent")
    Then the result is []

  Scenario: Ignore rules given by the caller join the repository's own
    Given a repository "r"
    And "r" commits "base" with .gitignore="*.tmp\n"
    When "r" calls ignored(["a.tmp", "b.txt", "build/x.o", "deep/c.tmp", "keep.o"], ["build/"])
    Then the result is ["a.tmp", "build/x.o", "deep/c.tmp"]

  Scenario: Fetch and push move commits between a clone and its origin
    Given a repository "r"
    And an origin "o"
    And "r" has the origin "o" as remote "origin"
    And "r" commits "first" with a.txt="1\n"
    And "r" calls push("HEAD", "main")
    And "other" is a clone of the origin "o"
    And "other" commits "theirs" with b.txt="2\n"
    And "other" calls push("HEAD", "main")
    When "r" calls fetch()
    And "r" calls rev_list_count("HEAD..origin/main")
    Then the result is 1
    When "r" calls log_subjects("HEAD..origin/main")
    Then the result is ["theirs"]
    When "r" commits "mine" with c.txt="3\n"
    And "r" tries push("HEAD", "main")
    Then the call fails as a remote error because "rejected"
    When "r" calls rebase("origin/main")
    And "r" calls push("HEAD", "main")
    And "r" calls rev_list_count("origin/main..HEAD")
    Then the result is 0
    When "other" calls fetch()
    And "other" calls log_subjects("origin/main", limit=2)
    Then the result is ["mine", "theirs"]

  Scenario: Fetching from a remote that does not exist fails
    Given a repository "r"
    And "r" commits "first" with a.txt="1\n"
    When "r" tries fetch("nowhere")
    Then the call fails
