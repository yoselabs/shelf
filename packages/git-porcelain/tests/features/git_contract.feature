@contract
Feature: One Repo and Worktree, real or fake
  Every intent operation a driver such as task-loop takes on a checkout behaves the same on the git binary
  (RealRepo) and in memory (FakeRepo). These scenarios run against both; @real_only names a gap of the fake.

  Scenario: Guarded remote deletion requires a full ref and preserves a stale lease
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "root"
    And the origin "o" advances "main" with b="remote"
    When "r" tries delete_remote_at("origin", "main", "<mem:root>")
    Then the call raises ValueError
    When "r" tries delete_remote_at("origin", "refs/heads/main", "<mem:root>")
    Then the call raises GitUnavailable
    When "r" calls fetch("origin")
    And "r" calls history(["origin/main"], limit=1)
    Then the result's 0.sha is not "<mem:root>"

  Scenario: Checked out branches cannot be deleted even at the expected tip
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "root"
    When "r" tries delete_branch("main", expected="<mem:root>")
    Then the call raises BranchPinned
    When "r" calls branches()
    Then the result is [["main", "<mem:root>"]]
    When "r" calls checkout_new("other")
    And "r" calls delete_branch("main", expected="<mem:root>")
    And "r" calls branches()
    Then the result is [["other", "<mem:root>"]]

  Scenario: Another worktree also prevents branch deletion
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "root"
    And "r" calls checkout_new("topic")
    And "r" calls checkout("main")
    And "r" adds a worktree "linked" at "topic" as "linked"
    And "linked" calls checkout("topic")
    When "r" tries delete_branch("topic", expected="<mem:root>")
    Then the call raises BranchPinned
    When "r" calls branches("topic")
    Then the result is [["topic", "<mem:root>"]]
    When "linked" calls branch()
    Then the result is "topic"

  Scenario Outline: Push safety requires explicit consent before invoking git
    Given a repository "r"
    When "r" tries <operation>
    Then the call raises ValueError

    Examples:
      | operation                                                         |
      | push_refspecs("origin", ["+HEAD:main"])                             |
      | push_request("origin", ["+HEAD:main"])                              |
      | push_refspecs("origin", [":main"])                                  |
      | push_refspecs("origin", ["+:main"], force=True)                      |
      | push_request("origin", ["+:main"], force=True)                       |
      | push_refspecs("origin", ["+:main"], allow_delete=True)               |
      | push_request("origin", ["+:main"], allow_delete=True)                |
      | push_request("origin", [":main"])                                   |
      | push_request("origin", ["main"], options=["--force"])                |
      | push_request("origin", ["main"], options=["-f"])                     |
      | push_request("origin", ["main"], options=["--delete"])               |
      | push_request("origin", ["main"], options=["-d"])                     |
      | push_request("origin", [], options=["--mirror"])                    |
      | push_request("origin", [], options=["--mirror"], force=True)         |
      | push_request("origin", [], options=["--mirror"], allow_delete=True)  |
      | push_request("origin", [], options=["--prune"])                     |

  Scenario Outline: Push opt ins permit their corresponding forms
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    When "r" calls <operation>
    Then the push succeeded

    Examples:
      | operation                                                                                  |
      | push_refspecs("origin", ["+HEAD:refs/heads/main"], force=True)                                |
      | push_request("origin", ["+HEAD:refs/heads/main"], force=True)                                 |
      | push_refspecs("origin", [":refs/heads/main"], allow_delete=True)                              |
      | push_request("origin", [":refs/heads/main"], allow_delete=True)                               |
      | push_request("origin", ["HEAD:refs/heads/main"], options=["--force"], force=True)              |
      | push_request("origin", ["HEAD:refs/heads/main"], options=["-f"], force=True)                   |
      | push_request("origin", ["main"], options=["--delete"], allow_delete=True)                     |
      | push_request("origin", ["main"], options=["-d"], allow_delete=True)                           |
      | push_request("origin", [], options=["--mirror"], force=True, allow_delete=True)               |
      | push_request("origin", ["HEAD:refs/heads/main"], options=["--prune"], allow_delete=True)       |
      | push_request("origin", ["HEAD:refs/heads/main"], options=["--force-with-lease"])               |
      | push_request("origin", ["HEAD:refs/heads/main"], options=["--force-with-lease=refs/heads/main:<head:r>"]) |

  Scenario: An explicit lease remains allowed and refuses a stale expected tip
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "root"
    And "r" commits "local" with b="local"
    And the origin "o" advances "main" with c="remote"
    When "r" calls push_request("origin", ["HEAD:refs/heads/main"], options=["--force-with-lease=refs/heads/main:<mem:root>"])
    Then the result's ok is False
    And the command output contains "stale info"

  Scenario: A deletion only push returns an empty sha
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    When "r" calls push_refspecs("origin", [":refs/heads/main"], allow_delete=True)
    Then the result is a Pushed
    And the result's sha is ""
    When "r" tries fetch("origin", refspecs=["refs/heads/main"])
    Then the call raises GitUnavailable

  Scenario Outline: Force options authorize replacing a remote tip
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "root"
    And the origin "o" advances "main" with b="remote"
    When "r" calls push_request("origin", ["HEAD:refs/heads/main"], options=["<option>"], force=True)
    Then the result's ok is True
    When "r" calls fetch("origin")
    And "r" calls history(["origin/main"], limit=1)
    Then the result's 0.sha is "<mem:root>"

    Examples:
      | option  |
      | --force |
      | -f      |

  Scenario Outline: Deletion options remove the advertised ref
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    When "r" calls push_request("origin", ["main"], options=["<option>"], allow_delete=True)
    Then the result's ok is True
    When "r" tries fetch("origin", refspecs=["refs/heads/main"])
    Then the call raises GitUnavailable

    Examples:
      | option   |
      | --delete |
      | -d       |

  Scenario Outline: Mirror and prune delete refs absent from their local scope
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" calls push_refspecs("origin", ["HEAD:refs/heads/stale"])
    When "r" calls push_request("origin", <refspecs>, options=["<option>"], force=<force>, allow_delete=True)
    Then the result's ok is True
    When "r" tries fetch("origin", refspecs=["refs/heads/stale"])
    Then the call raises GitUnavailable
    When "r" calls fetch("origin", refspecs=["refs/heads/main"])
    Then the result is None

    Examples:
      | option   | refspecs                      | force |
      | --mirror | []                            | True  |
      | --prune  | ["refs/heads/*:refs/heads/*"]   | False |

  Scenario Outline: Remote option injection is rejected
    Given a repository "r"
    When "r" tries <operation>
    Then the call raises ValueError

    Examples:
      | operation                                                        |
      | sync("--receive-pack=false")                                     |
      | fetch("--receive-pack=false")                                    |
      | push("main", remote="--receive-pack=false")                       |
      | push_refspecs("--receive-pack=false", ["HEAD:main"])               |
      | push_request("--receive-pack=false", ["HEAD:main"])                |
      | delete_remote_at("--receive-pack=false", "refs/heads/main", "abc") |

  Scenario Outline: Invalid bases fail before branch or history mutation
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "before"
    When "r" tries <operation>
    Then the call raises MissingRevision
    When "r" calls branch()
    Then the result is "main"
    When "r" calls snapshot("HEAD")
    Then the result's head is "<mem:before>"

    Examples:
      | operation                                                  |
      | take_branch(branch="topic", base="--orphan", mode="restart") |
      | take_branch(branch="main", base="missing", mode="resume")    |
      | rebase_onto("--exec=false", squash_message="squash")          |

  Scenario: A signer failure is infrastructure failure rather than hook rejection
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "before"
    And "r" writes b="pending"
    And the signer of "r" fails
    When "r" tries record("signed", paths="all", hooks=True)
    Then the call raises GitUnavailable
    When "r" calls snapshot("HEAD")
    Then the result's head is "<mem:before>"
    And the index of "r" reads "b" as "pending"

  Scenario: Fresh rebase observations and command refusals are explicit
    Given a repository "r"
    When "r" calls rebasing()
    Then the result is False
    When "r" calls unmerged()
    Then the result is []
    When "r" calls abort_rebase()
    Then the result's ok is True
    When "r" calls continue_rebase()
    Then the result's ok is False
    When "r" calls rebase("missing")
    Then the result's ok is False

  Scenario: Merge base permits missing revisions and cherry preserves oldest first picks
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "root"
    And "r" commits "first" with b="first"
    And "r" remembers its head as "first"
    And "r" commits "second" with c="second"
    When "r" calls merge_base("missing", "HEAD")
    Then the result is None
    When "r" calls merge_base("<mem:root>", "HEAD")
    Then the result is "<mem:root>"
    When "r" calls cherry("<mem:root>", "HEAD")
    Then the oid of each result entry is ["<mem:first>", "<head:r>"]
    And the upstream of each result entry is [False, False]

  Scenario: Named remote URL absence is typed
    Given a repository "r"
    When "r" tries remote_url("missing")
    Then the call raises MissingRemote

  Scenario Outline: Observation faults stay failures instead of becoming absence
    Given a repository "r"
    And "r" commits "root" with a="root"
    And the observations of "r" will fail
    When "r" tries <operation>
    Then the call raises GitReadFailure

    Examples:
      | operation                 |
      | merge_base("HEAD", "HEAD") |
      | remote_url("origin")       |
      | rebasing()                 |
      | unmerged()                 |

  Scenario: Explicit refspecs keep source commits and guarded deletion keeps moved refs
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "root"
    And "r" commits "local" with b="local"
    When "r" calls remote_url("origin")
    Then the result is "<mem:origin:o>"
    When "r" calls push_refspecs("origin", ["<mem:root>:refs/heads/pinned"])
    Then the result is a Pushed
    When "r" calls fetch("origin", refspecs=["refs/heads/pinned"])
    Then the result is None
    When "r" calls delete_remote_at("origin", "refs/heads/pinned", "<mem:root>")
    Then the result is None
    When "r" calls delete_remote_at("origin", "refs/heads/pinned", "<mem:root>")
    Then the result is None

  Scenario: Push requests preserve namespaces multiple refs and deletion
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    When "r" calls push_request("origin", ["HEAD:refs/heads/one", "+HEAD:refs/tags/two"], force=True)
    Then the result's ok is True
    When "r" calls push_request("origin", [":refs/heads/one", ":refs/tags/two"], allow_delete=True)
    Then the result's ok is True

  Scenario: A lease refuses a branch changed since fetching
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" commits "local" with b="local"
    And the origin "o" advances "main" with c="elsewhere"
    When "r" calls push_lease("origin", "HEAD:refs/heads/main")
    Then the result's ok is False
    And the command output contains "stale info"

  Scenario Outline: Configured landing push forms retain HEAD destinations and options
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" commits "local" with b="local"
    When "r" calls push_request(<remote>, <refspecs>, options=<options>, force=<force>)
    Then the result's ok is True

    Examples:
      | remote   | refspecs          | options        | force |
      | "origin" | ["HEAD"]          | []             | False |
      | "origin" | ["HEAD:main"]     | []             | False |
      | "origin" | ["+HEAD:main"]    | []             | True  |
      | "origin" | []                | []             | False |
      | None     | []                | []             | False |
      | None     | ["HEAD:main"]     | ["--dry-run"]  | False |

  Scenario: Remote policy refusal is distinct from a ref race
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "before"
    And "r" commits "local" with b="local"
    And "r" calls push_request("origin", ["HEAD:refs/heads/main"])
    And the origin "o" refuses non fast forward pushes
    When "r" calls push_refspecs("origin", ["+<mem:before>:refs/heads/main"], force=True)
    Then the result is a RemoteRejected

  Scenario: An explicit push reports a ref race separately
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" commits "local" with b="local"
    And the origin "o" advances "main" with c="remote"
    When "r" calls push_refspecs("origin", ["HEAD:refs/heads/main"])
    Then the result is a RefRejected

  Scenario: Cherry recognizes equivalent patches on separate branches
    Given a repository "r"
    And "r" commits "root" with a="root\n"
    And "r" calls checkout_new("topic")
    And "r" commits "mine" with b="shared\n"
    And "r" remembers its head as "mine"
    And "r" calls checkout("main")
    And "r" commits "equivalent" with b="shared\n"
    When "r" calls cherry("main", "topic")
    Then the oid of each result entry is ["<mem:mine>"]
    And the upstream of each result entry is [True]

  Scenario: No common ancestor is a known absence
    Given an origin "o"
    And the origin "o" holds a="remote"
    And a repository "r"
    And "r" commits "unrelated" with b="local"
    And "r" has the origin "o" as remote "origin"
    And "r" calls fetch()
    When "r" calls merge_base("HEAD", "origin/main")
    Then the result is None

  Scenario: Named remote URLs honor rewrite rules
    Given an origin "o"
    And "r" is a clone of the origin "o"
    And "r" config "url.expanded/.insteadOf" is "<root>/"
    When "r" calls remote_url("origin")
    Then the result is "expanded/o.git"

  Scenario: Scoped fetch writes FETCH_HEAD without moving the checkout
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "root"
    And the origin "o" advances "main" with b="remote"
    When "r" calls fetch("<mem:origin:o>", refspecs=["main"])
    Then the result is None
    When "r" calls history(["FETCH_HEAD"], limit=1)
    Then the result's 0.subject is "advance"
    When "r" calls branch()
    Then the result is "main"

  Scenario: LFS failure remains an outcome
    Given a repository "r"
    When "r" calls lfs_push("absent", ["HEAD", "refs/heads/main"])
    Then the result's ok is False

  Scenario: LFS timeout is an outcome and invocation failure still raises
    Given a repository "r"
    And the LFS command of "r" will time out
    When "r" calls lfs_push("origin", ["HEAD", "refs/heads/main"])
    Then the result's ok is False
    And the result's output is "git lfs timed out after 60 min"
    Given the LFS command of "r" cannot start
    When "r" tries lfs_push("origin", ["HEAD"])
    Then the call raises GitUnavailable

  Scenario: LFS uploads can succeed without installing hooks
    Given a repository "r"
    And the LFS command of "r" will succeed
    When "r" calls lfs_push("origin", ["HEAD", "refs/heads/main"])
    Then the result's ok is True

  Scenario Outline: Rebase update-refs inherits configuration and permits explicit overrides
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" calls checkout_new("topic")
    And "r" commits "first" with b="first"
    And "r" calls checkout_new("middle")
    And "r" remembers its head as "middle"
    And "r" calls checkout("topic")
    And "r" commits "second" with c="second"
    And "r" calls checkout("main")
    And "r" commits "base" with d="base"
    And "r" calls checkout("topic")
    And "r" config "rebase.updateRefs" is "true"
    When "r" calls rebase_onto("main", update_refs=<option>)
    Then the result is a Rebased
    And the branch "middle" of "r" rewritten is <rewritten>

    Examples:
      | option | rewritten |
      | None   | True      |
      | False  | False     |
      | True   | True      |

  Scenario Outline: A failed squash restores the original work before applying its failure policy
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" commits "first" with b="first"
    And "r" commits "second" with c="second"
    And "r" remembers its head as "before"
    And the origin "o" advances "main" with d="base"
    And "r" calls fetch()
    And the squash commit of "r" will fail
    When "r" tries rebase_onto("origin/main", squash_message="combined", squash_failure="<policy>")
    Then the squash policy outcome is "<outcome>"
    And the file "b" of "r" holds "first"
    And the file "c" of "r" holds "second"

    Examples:
      | policy             | outcome |
      | raise              | raised  |
      | continue_unsquashed | rebased |

  Scenario: Raw rebase continuation uses only the caller's staged resolution
    Given an origin "o"
    And the origin "o" holds a="root\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a="mine\n"
    And "r" remembers its head as "before"
    And the origin "o" advances "main" with a="theirs\n"
    And "r" calls fetch()
    When "r" calls rebase("origin/main")
    Then the result's ok is False
    When "r" calls rebasing()
    Then the result is True
    When "r" calls unmerged()
    Then the result is ["a"]
    When "r" calls continue_rebase(check_markers=True, stage_conflicts=True)
    Then the result's ok is False
    When "r" writes a="resolved\n"
    And "r" calls continue_rebase()
    Then the result's ok is False
    When "r" stages ["a"]
    And "r" writes a="unstaged\n"
    And "r" calls continue_rebase()
    Then the result's ok is False
    When "r" writes a="resolved\n"
    And "r" calls continue_rebase()
    Then the result's ok is True
    When "r" calls rebasing()
    Then the result is False
    When "r" calls abort_rebase(restore_to="<mem:before>")
    Then the result's ok is True
    And the file "a" of "r" holds "mine\n"

  Scenario: Rebase abort restores HEAD and clears conflict observations
    Given an origin "o"
    And the origin "o" holds a="root\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a="mine\n"
    And "r" remembers its head as "before"
    And the origin "o" advances "main" with a="theirs\n"
    And "r" calls fetch()
    And "r" calls rebase_onto("origin/main")
    When "r" calls abort_rebase(restore_to="<mem:before>")
    Then the result's ok is True
    When "r" calls unmerged()
    Then the result is []
    When "r" calls rebasing()
    Then the result is False

  Scenario: Continuation explicitly stages an edited resolution
    Given an origin "o"
    And the origin "o" holds a="root\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a="mine\n"
    And the origin "o" advances "main" with a="theirs\n"
    And "r" calls fetch()
    And "r" calls rebase_onto("origin/main")
    When "r" writes a="resolved\n"
    And "r" calls continue_rebase(stage_conflicts=True, check_markers=True)
    Then the result's ok is True
    When "r" calls continue_rebase(missing_ok=True)
    Then the result's ok is True
    When "r" calls abort_rebase(missing_ok=False)
    Then the result's ok is False

  Scenario: A guarded remote deletion refuses an advanced destination
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "before"
    And the origin "o" advances "main" with b="other"
    When "r" tries delete_remote_at("origin", "refs/heads/main", "<mem:before>")
    Then the call raises GitUnavailable

  Scenario: Failed deletion verification cannot report authoritative absence
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "before"
    And the origin "o" is offline
    When "r" tries delete_remote_at("origin", "refs/heads/main", "<mem:before>")
    Then the call raises GitReadFailure

  Scenario: Scoped fetch refuses a missing remote ref
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    When "r" tries fetch("origin", refspecs=["missing"])
    Then the call raises GitUnavailable

  Scenario: Explicit pushes preserve hook environment and distinguish policy from races
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with b="local"
    And "r" has a pre-push hook that wants env
    When "r" calls push_refspecs("origin", ["HEAD:refs/heads/main"])
    Then the result is a HookRejected
    When "r" calls push_refspecs("origin", ["HEAD:refs/heads/main"], hook_env={"X": "1"})
    Then the result is a Pushed

  Scenario: A lease can replace a fetched destination without setting an upstream
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "before"
    And "r" commits "mine" with b="local"
    And "r" calls push_lease("origin", "HEAD:refs/heads/main")
    And "r" calls reset("<mem:before>", mode="hard")
    When "r" calls push_lease("origin", "HEAD:refs/heads/main")
    Then the result's ok is True

  Scenario Outline: Checkout observations never manufacture absence outside a repository
    Given "plain" is the plain folder
    When "plain" tries <operation>()
    Then the call raises GitReadFailure

    Examples:
      | operation |
      | unmerged  |
      | rebasing  |

  Scenario: Branch names survive unborn HEAD and become absent when detached
    Given a repository "r"
    When "r" calls branch()
    Then the result is "main"
    When "r" commits "root" with a="one"
    And "r" remembers its head as "root"
    And "r" calls checkout("<mem:root>")
    And "r" calls branch()
    Then the result is None
    When "r" calls checkout("main")
    And "r" calls branch()
    Then the result is "main"

  Scenario: New branches are exclusive and ordinary checkout never creates one
    Given a repository "r"
    And "r" commits "root" with a="one"
    When "r" calls checkout_new("topic")
    And "r" calls branch()
    Then the result is "topic"
    When "r" tries checkout_new("topic")
    Then the call raises BranchExists
    When "r" tries checkout("absent")
    Then the call raises MissingRevision
    When "r" calls branch()
    Then the result is "topic"

  Scenario: Checkout refuses to overwrite local changes
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" calls checkout_new("topic")
    And "r" commits "topic" with a="two"
    And "r" calls checkout("main")
    And "r" writes a="local"
    When "r" tries checkout("topic")
    Then the call raises DirtyTree
    And the file "a" of "r" holds "local"

  Scenario: Checkout refuses another worktree's branch
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And "w" calls checkout_new("topic")
    When "r" tries checkout("topic")
    Then the call raises BranchPinned
    When "r" tries checkout_force("topic", "main")
    Then the call raises BranchPinned
    When "w" calls branch()
    Then the result is "topic"

  Scenario: Creating from an explicit start switches files while compatible local edits survive checkout
    Given a repository "r"
    And "r" commits "root" with a="one", unchanged="base"
    And "r" remembers its head as "root"
    And "r" commits "next" with a="two"
    And "r" writes unchanged="local", untracked="keep"
    When "r" calls checkout_new("topic", "<mem:root>")
    Then the file "a" of "r" holds "one"
    And the file "unchanged" of "r" holds "local"
    And the file "untracked" of "r" holds "keep"
    When "r" calls checkout("HEAD")
    And "r" calls branch()
    Then the result is "topic"
    When "r" calls checkout("main")
    Then the file "a" of "r" holds "two"
    And the file "unchanged" of "r" holds "local"

  Scenario: Clean respects keep patterns and optionally removes ignored files without moving HEAD
    Given a repository "r"
    And "r" commits "root" with .gitignore="*.cache\n" tracked="one"
    And "r" remembers its head as "root"
    And "r" writes drop/file="trash", keep/file="keep", ignored.cache="cache", saved.cache="saved"
    When "r" calls clean(["keep/", "saved.cache"])
    Then the file "drop/file" of "r" is absent
    And the file "keep/file" of "r" holds "keep"
    And the file "ignored.cache" of "r" holds "cache"
    When "r" calls clean(["keep/", "saved.cache"], ignored=True)
    Then the file "ignored.cache" of "r" is absent
    And the file "saved.cache" of "r" holds "saved"
    And the file "tracked" of "r" holds "one"
    When "r" calls history(["HEAD"], limit=1)
    Then the result's 0.sha is "<mem:root>"
    When "r" calls branch()
    Then the result is "main"

  Scenario Outline: Reset modes separately control HEAD index and files
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" remembers its head as "root"
    And "r" commits "next" with a="two"
    And "r" writes a="local", untracked="keep"
    When "r" calls reset("<mem:root>", mode="<mode>")
    Then the file "a" of "r" holds "<files>"
    And the file "untracked" of "r" holds "keep"
    And the index of "r" reads "a" as "<index>"
    When "r" calls history(["HEAD"], limit=1)
    Then the result's 0.sha is "<mem:root>"

    Examples:
      | mode  | files | index |
      | soft  | local | two   |
      | mixed | local | one   |
      | hard  | one   | one   |

  Scenario: Forced checkout resets an existing branch and discards tracked edits
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" remembers its head as "root"
    And "r" calls checkout_new("topic")
    And "r" commits "next" with a="two"
    And "r" writes a="local", untracked="keep"
    When "r" calls checkout_force("topic", "<mem:root>")
    Then the file "a" of "r" holds "one"
    And the file "untracked" of "r" holds "keep"
    When "r" calls branch()
    Then the result is "topic"
    When "r" calls checkout_force("new", "main")
    And "r" calls branch()
    Then the result is "new"

  Scenario: Renaming updates a checked out branch and refuses a taken name
    Given a repository "r"
    And "r" commits "root" with a="one"
    When "r" calls rename_branch("main", "renamed")
    And "r" calls branch()
    Then the result is "renamed"
    When "r" calls checkout_new("topic")
    And "r" tries rename_branch("renamed", "topic")
    Then the call raises BranchExists
    When "r" tries rename_branch("absent", "other")
    Then the call raises MissingRevision

  Scenario: Branch deletion compares its tip and never retries a stale expectation
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" remembers its head as "root"
    And "r" calls checkout_new("topic")
    And "r" commits "next" with a="two"
    And "r" remembers its head as "next"
    And "r" calls checkout("main")
    When "r" tries delete_branch("topic", expected="<mem:root>")
    Then the call raises RefRace
    And the failure cannot be retried
    When "r" calls branches("topic")
    Then the result is [["topic", "<mem:next>"]]
    When "r" calls delete_branch("topic", expected="<mem:next>")
    And "r" calls branches("topic")
    Then the result is []
    When "r" tries delete_branch("topic", expected="<mem:next>")
    Then the call raises RefRace
    And the failure cannot be retried

  Scenario: Reset defaults to mixed and can run while detached
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" remembers its head as "root"
    And "r" commits "next" with a="two"
    And "r" remembers its head as "next"
    And "r" calls checkout("<mem:next>")
    When "r" calls reset("<mem:root>")
    Then the file "a" of "r" holds "two"
    And the index of "r" reads "a" as "one"
    When "r" calls branch()
    Then the result is None

  Scenario: Staged recording works on an unborn branch and can explicitly create an empty commit
    Given a repository "r"
    And "r" writes a="staged", untracked="keep"
    And "r" stages ["a"]
    When "r" calls record("root", paths="staged")
    Then the result is a Recorded
    When "r" calls tree("HEAD")
    Then the tree lists ["a"]
    When "r" calls record("empty", paths="staged", allow_empty=True)
    Then the result is a Recorded
    When "r" calls history(["HEAD"])
    Then the subject of each result entry is ["empty", "root"]

  Scenario: Staged recording preserves the staged contents and leaves unstaged work alone
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" writes a="staged", added="new"
    And "r" stages ["a", "added"]
    And "r" writes a="unstaged", untracked="keep"
    When "r" calls record("staged only", paths="staged")
    Then the result is a Recorded
    And the index of "r" reads "a" as "staged"
    And the file "a" of "r" holds "unstaged"
    When "r" calls tree("HEAD")
    Then the tree reads "a" as "staged"
    And the tree reads "added" as "new"
    And the tree reads "untracked" as nothing
    When "r" calls record("no staged changes", paths="staged")
    Then the result is a NothingToRecord

  Scenario: Tracked recording includes deletions and staged additions but excludes untracked files
    Given a repository "r"
    And "r" commits "root" with a="one", deleted="old"
    And "r" writes added="new"
    And "r" stages ["added"]
    And "r" writes a="changed", untracked="keep"
    And "r" removes "deleted"
    When "r" calls record("tracked only", paths="tracked")
    Then the result is a Recorded
    When "r" calls tree("HEAD")
    Then the tree lists ["a", "added"]
    And the tree reads "a" as "changed"
    And the file "untracked" of "r" holds "keep"

  Scenario: Amend can change only the message or keep the message while folding staged work
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" commits "original" with a="two"
    When "r" calls record("renamed", paths="staged", mode="amend")
    Then the result is a Recorded
    When "r" calls history(["HEAD"])
    Then the subject of each result entry is ["renamed", "root"]
    When "r" writes a="staged"
    And "r" stages ["a"]
    And "r" writes a="unstaged"
    And "r" calls record("", paths="staged", mode="amend")
    Then the result is a Recorded
    And the file "a" of "r" holds "unstaged"
    When "r" calls history(["HEAD"])
    Then the subject of each result entry is ["renamed", "root"]
    When "r" calls tree("HEAD")
    Then the tree reads "a" as "staged"

  Scenario: A refusing hook leaves the staged index and unstaged work intact
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" remembers its head as "root"
    And "r" writes a="staged"
    And "r" stages ["a"]
    And "r" writes a="unstaged"
    And "r" has a pre-commit hook that refuses
    When "r" calls record("blocked", paths="staged", hooks=True)
    Then the result is a HookRejected
    And the index of "r" reads "a" as "staged"
    And the file "a" of "r" holds "unstaged"
    When "r" calls history(["HEAD"], limit=1)
    Then the result's 0.sha is "<mem:root>"
    When "r" calls record("accepted", paths="staged")
    Then the result is a Recorded

  Scenario: New checkout and reset report a missing start without changing branches
    Given a repository "r"
    And "r" commits "root" with a="one"
    When "r" tries checkout_new("topic", "absent")
    Then the call raises MissingRevision
    When "r" tries reset("absent")
    Then the call raises MissingRevision
    When "r" tries checkout_force("topic", "absent")
    Then the call raises MissingRevision
    When "r" calls branch()
    Then the result is "main"

  Scenario: Index locks stop checkout and reset with a typed retryable failure
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" holds an index lock
    When "r" tries checkout_new("topic")
    Then the call raises IndexLocked
    And the failure may be retried
    When "r" tries reset("HEAD", mode="hard")
    Then the call raises IndexLocked
    And the failure may be retried

  Scenario Outline: Checkout primitives fail loudly outside a repository
    Given "plain" is the plain folder
    When "plain" tries <call>
    Then the call raises NotARepo

    Examples:
      | call                                 |
      | branch()                             |
      | checkout("main")                     |
      | checkout_new("topic")                |
      | clean()                              |
      | reset("HEAD")                        |
      | checkout_force("topic", "HEAD")      |
      | record("work", paths="staged")       |

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

  Scenario: A declared snapshot input that does not exist is unavailable
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n"
    When "r" tries snapshot("HEAD", inputs=["missing.input"])
    Then the call raises GitUnavailable

  Scenario: A declared snapshot directory includes ignored descendants
    Given a repository "r"
    And "r" commits "base" with a.txt="a\n", .gitignore="*.log\n"
    And "r" writes inputs/visible.txt="visible\n", inputs/nested/ignored.log="ignored\n", outside.log="outside\n"
    And "r" remembers snapshot("HEAD").tree as "ordinary"
    When "r" remembers snapshot("HEAD", inputs=["inputs"]).tree as "declared"
    And "r" calls tree("<mem:declared>")
    Then the tree lists [".gitignore", "a.txt", "inputs/nested/ignored.log", "inputs/visible.txt"]
    And the tree reads "inputs/nested/ignored.log" as "ignored\n"
    When "r" writes inputs/nested/ignored.log="changed\n"
    And "r" calls snapshot("HEAD", inputs=["inputs"])
    Then the result's tree is not "<mem:declared>"
    When "r" calls snapshot("HEAD")
    Then the result's tree is "<mem:ordinary>"
    When "r" calls dirty()
    Then the result's tracked is []
    And the result's untracked is ["inputs/visible.txt"]

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
    Then the call raises MissingRevision

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
    Then the call raises IndexLocked
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
    Then the call raises MissingRevision

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
    Then the call raises WorktreeRemoveRefused
    And the refusal reason is "fatal: '<root>/w' contains modified or untracked files, use --force to delete it"
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

  Scenario: A missing registered checkout needs force to be added again
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And the folder of "w" is deleted behind git's back
    When "r" tries add_worktree("<root>/w", "HEAD")
    Then the call raises GitUnavailable
    When "r" calls add_worktree("<root>/w", "HEAD", force=True)
    And "r" calls worktrees(with_dirty=True)
    Then the path of each result entry is ["<root>/r", "<root>/w"]
    And the dirty of each result entry is [False, False]
    And the file "a.txt" of "w" holds "1\n"

  Scenario: Force does not replace a live checkout
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    When "r" tries add_worktree("<root>/w", "HEAD", force=True)
    Then the call raises GitUnavailable
    And the file "a.txt" of "w" holds "1\n"

  Scenario: Pruning alone forgets missing registrations and keeps live checkouts
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "gone" at "HEAD" as "gone"
    And "r" adds a worktree "live" at "HEAD" as "live"
    And the folder of "gone" is deleted behind git's back
    When "r" calls worktrees()
    Then the result has 3 entries
    When "r" calls prune_worktrees()
    And "r" calls worktrees()
    Then the path of each result entry is ["<root>/r", "<root>/live"]

  Scenario: Strict removal refuses an unregistered absent path without pruning
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "gone" at "HEAD" as "gone"
    And the folder of "gone" is deleted behind git's back
    When "r" tries drop_worktree("<root>/unknown", missing_ok=False)
    Then the call raises WorktreeRemoveRefused
    And the refusal reason is "fatal: '<root>/unknown' is not a working tree"
    When "r" calls worktrees()
    Then the result has 2 entries

  Scenario: Default removal accepts an absent unregistered path and prunes
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "gone" at "HEAD" as "gone"
    And the folder of "gone" is deleted behind git's back
    When "r" calls drop_worktree("<root>/unknown")
    And "r" calls worktrees()
    Then the result has 1 entries

  Scenario: Strict removal removes only its target without pruning other registrations
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "gone" at "HEAD" as "gone"
    And "r" adds a worktree "live" at "HEAD" as "live"
    And the folder of "gone" is deleted behind git's back
    When "r" calls drop_worktree("<root>/live", missing_ok=False)
    And "r" calls worktrees()
    Then the path of each result entry is ["<root>/r", "<root>/gone"]
    When "r" calls drop_worktree("<root>/gone", missing_ok=False)
    And "r" calls worktrees()
    Then the result has 1 entries

  Scenario: Strict removal preserves a dirty checkout and exposes its refusal
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And "w" writes a.txt="edited\n"
    When "r" tries drop_worktree("<root>/w", missing_ok=False)
    Then the call raises WorktreeRemoveRefused
    And the refusal reason is "fatal: '<root>/w' contains modified or untracked files, use --force to delete it"
    And the file "a.txt" of "w" holds "edited\n"
    When "r" calls drop_worktree("<root>/w", missing_ok=False, force=True)
    And "r" calls worktrees()
    Then the result has 1 entries

  Scenario: Worktree paths round trip quotes tabs newlines and Unicode
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "pool \"quoted\"\té\nslot" at "HEAD" as "w"
    When "r" calls worktrees()
    Then the path of each result entry is ["<root>/r", "<root>/pool \"quoted\"\té\nslot"]

  Scenario: Pool operations and state stay pinned under a stray core.worktree
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And a folder "elsewhere"
    And "r" config "core.worktree" is "<root>/elsewhere"
    When "r" adds a worktree "w" at "HEAD" as "w"
    And "r" calls worktree_state("<root>/w")
    Then the result is b"# branch.oid <head:r>\x00# branch.head (detached)\x00"
    When "r" calls prune_worktrees()
    And "r" calls worktrees()
    Then the path of each result entry is ["<root>/r", "<root>/w"]
    When "r" calls drop_worktree("<root>/w", missing_ok=False)
    And "r" calls worktrees()
    Then the result has 1 entries

  Scenario: Status state is raw NUL terminated bytes with HEAD and branch
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    When "r" calls worktree_state("<root>/r")
    Then the result is b"# branch.oid <head:r>\x00# branch.head main\x00"
    When "r" writes a.txt="edited\n", "new file.txt"="new\n"
    And "r" calls worktree_state("<root>/r")
    Then the status bytes list tracked ["a.txt"] and untracked ["new file.txt"]
    When "r" calls worktree_state("<root>/absent")
    Then the result is None

  Scenario: Status state preserves staged rename records and their NUL separated original path
    Given a repository "r"
    And "r" commits "one" with "old name.txt"="1\n"
    And "r" stages a rename from "old name.txt" to "new name.txt"
    When "r" calls worktree_state("<root>/r")
    Then the status records with object ids normalized are b"2 R. N... 100644 100644 100644 <oid> <oid> R100 new name.txt\x00old name.txt\x00"

  # The fake keeps an unmerged path set, not the three index stages. Object ids may
  # differ; both implementations must emit the same fields, modes and record framing.
  Scenario: Status state preserves unmerged records during a conflicted rebase
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a.txt="mine\n"
    And the origin "o" advances "main" with a.txt="theirs\n"
    And "r" calls sync()
    When "r" calls rebase_onto("origin/main")
    Then the result is a Conflict
    When "r" calls worktree_state("<root>/r")
    Then the status records with object ids normalized are b"u UU N... 100644 100644 100644 100644 <oid> <oid> <oid> a.txt\x00"

  Scenario: Status state handles unborn detached ignored and missing checkouts
    Given a repository "r"
    When "r" calls worktree_state("<root>/r")
    Then the result is b"# branch.oid (initial)\x00# branch.head main\x00"
    When "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    And "r" calls exclude_locally(["ignored/"])
    And "w" writes ignored/x="x\n"
    And "r" calls worktree_state("<root>/w")
    Then the result is b"# branch.oid <head:r>\x00# branch.head (detached)\x00"
    When the folder of "w" is deleted behind git's back
    And "r" calls worktree_state("<root>/w")
    Then the result is None

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
    Then the call raises NotARepo
    When "plain" tries snapshot("HEAD")
    Then the call raises NotARepo

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
