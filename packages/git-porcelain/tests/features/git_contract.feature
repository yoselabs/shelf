@contract
Feature: One Repo and Worktree, real or fake
  Every intent operation a driver such as task-loop takes on a checkout behaves the same on the git binary
  (RealRepo) and in memory (FakeRepo). These scenarios run against both; @real_only names a gap of the fake.

  Scenario: Literal staging includes deletions and leaves other working files alone
    Given a repository "r"
    And "r" commits "root" with gone="old", keep="old"
    And "r" removes "gone"
    And "r" writes keep="edited", "[literal]"="new", other="untracked"
    When "r" calls stage(["gone", "[literal]"])
    And "r" calls record("selected", paths="staged")
    Then the result is a Recorded
    When "r" calls tree("HEAD")
    Then the tree lists ["[literal]", "keep"]
    And the tree reads "keep" as "old"
    When "r" calls stage([])
    And "r" calls stage_tracked()
    And "r" calls record("tracked", paths="staged")
    Then the result is a Recorded
    When "r" calls tree("HEAD")
    Then the tree lists ["[literal]", "keep"]
    And the tree reads "keep" as "edited"

  Scenario: Staging a missing path reports failure
    Given a repository "r"
    When "r" tries stage(["missing"])
    Then the call raises GitUnavailable

  Scenario: Staging supports NUL delimited names and optional wildcard matching
    Given a repository "r"
    And "r" has many literal paths waiting to stage
    When "r" stages all the many literal paths
    And "r" calls record("many", paths="staged")
    Then the result is a Recorded
    And all the many literal paths were committed
    When "r" writes first.txt="one", second.txt="two", other="keep"
    And "r" calls stage(["*.txt"], literal=False)
    And "r" calls record("glob", paths="staged")
    Then the result is a Recorded
    When "r" calls dirty()
    Then the result's untracked is ["other"]

  Scenario: Tags are exclusive and missing revisions cannot create tags
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" remembers its head as "root"
    When "r" calls tag("release", "HEAD")
    And "r" calls refs(["refs/tags/"])
    Then the result is [{"name": "refs/tags/release", "sha": "<mem:root>"}]
    When "r" tries tag("release", "HEAD")
    Then the call raises TagExists
    When "r" tries tag("absent", "missing")
    Then the call raises MissingRevision
    When "r" calls refs([])
    Then the name of each result entry is ["refs/heads/main", "refs/tags/release"]
    When "r" calls refs(["refs/absent/"])
    Then the result is []

  Scenario: Ref listings accept arbitrary namespaces and multiple prefixes
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" calls fetch("origin", refspecs=["main:refs/custom/task"])
    And "r" calls tag("release", "HEAD")
    When "r" calls refs(["refs/custom/", "refs/tags/"])
    Then the name of each result entry is ["refs/custom/task", "refs/tags/release"]
    And the sha of each result entry is ["<head:r>", "<head:r>"]

  Scenario: Counts use explicit include and exclude sets without implicit HEAD
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" commits "child" with b="two"
    When "r" calls count(["HEAD", "main"], ["HEAD~1"])
    Then the result is 1
    When "r" calls count([])
    Then the result is 0
    When "r" calls count(["HEAD~1..HEAD", "HEAD~1"])
    Then the result is 1
    When "r" calls count(["HEAD", "^HEAD~1"])
    Then the result is 1
    When "r" tries count(["missing"])
    Then the call raises MissingRevision
    When "r" tries count(["HEAD"], ["missing"])
    Then the call raises MissingRevision

  Scenario: Fast forward merging preserves divergence as a typed error
    Given a repository "r"
    And "r" commits "root" with a="one"
    And "r" remembers its head as "root"
    And "r" commits "child" with b="two"
    And "r" remembers its head as "child"
    And "r" calls reset("<mem:root>", mode="hard")
    When "r" calls merge_ff("<mem:child>")
    And "r" calls count(["HEAD"])
    Then the result is 2
    When "r" calls reset("<mem:root>", mode="hard")
    And "r" commits "different" with c="three"
    And "r" tries merge_ff("<mem:child>")
    Then the call raises NotFastForward
    When "r" tries merge_ff("missing")
    Then the call raises MissingRevision

  Scenario: Remote advertisements accept patterns and report unreachable repositories
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    When "r" calls ls_remote("origin", ["main"])
    Then the name of each result entry is ["refs/heads/main"]
    And the oid of each result entry is ["<head:r>"]
    And the result's output is "<head:r>\trefs/heads/main"
    When "r" calls ls_remote("origin", ["absent"])
    Then the result is []
    When "r" calls ls_remote("origin")
    Then the name of each result entry is ["HEAD", "refs/heads/main"]
    When the origin "o" goes offline
    And "r" tries ls_remote("origin")
    Then the call raises GitUnavailable

  Scenario: Remote advertisements use the repository's injected environment
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" reaches origin "o" only through its injected environment
    When "r" calls ls_remote("injected", ["main"])
    Then the name of each result entry is ["refs/heads/main"]
    And the oid of each result entry is ["<head:r>"]

  Scenario: Staging and fast forward merging stay pinned under stray configuration
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "root"
    And "r" commits "child" with b="new"
    And "r" remembers its head as "child"
    And "r" calls reset("<mem:root>", mode="hard")
    And a folder "elsewhere"
    And "r" config "core.worktree" is "<root>/elsewhere"
    When "r" calls merge_ff("<mem:child>")
    Then the file "b" of "r" holds "new"
    When "r" writes a="edited"
    And "r" calls stage_tracked()
    Then the index of "r" reads "a" as "edited"
    When "r" writes literal="added"
    And "r" calls stage(["literal"])
    Then the index of "r" reads "literal" as "added"

  Scenario Outline: Recording preserves all hook output on success and refusal
    Given a repository "r"
    And "r" commits "root" with a="old"
    And "r" writes a="new"
    And "r" stages ["a"]
    And the verbose commit hook of "r" <outcome>
    When "r" calls record("work", paths="<scope>", mode="<mode>", hooks=True)
    Then the result is a <kind>
    And the complete hook output is preserved

    Examples:
      | outcome  | scope   | mode  | kind         |
      | accepts  | staged  | new   | Recorded     |
      | refuses  | staged  | new   | HookRejected |
      | accepts  | tracked | amend | Recorded     |
      | refuses  | tracked | amend | HookRejected |

  Scenario: Non hook commit failures also preserve complete combined output
    Given a repository "r"
    And "r" commits "root" with a="old"
    And "r" writes a="new"
    And the commit command of "r" fails with a long diagnostic
    When "r" tries record("work", paths="tracked", hooks=True)
    Then the call raises GitUnavailable
    And the complete commit failure output is preserved

  Scenario Outline: Recording marker text leaves the commit decision to git
    Given a repository "r"
    And "r" commits "root" with a="old"
    And "r" writes a="<<<<<<< ours\nmine\n=======\ntheirs\n>>>>>>> theirs\n"
    And "r" stages ["a"]
    When "r" calls record("markers", paths="<scope>", mode="<mode>")
    Then the result is a Recorded
    When "r" calls tree("HEAD")
    Then the tree reads "a" as "<<<<<<< ours\nmine\n=======\ntheirs\n>>>>>>> theirs\n"

    Examples:
      | scope   | mode  |
      | staged  | new   |
      | tracked | amend |

  Scenario: Amending an unborn branch exposes git's refusal after staging
    Given a repository "r"
    And "r" writes a="pending"
    When "r" tries record("amend", paths="tracked", mode="amend", hooks=True)
    Then the call raises GitUnavailable
    When "r" tries record("amend", paths="staged", mode="amend")
    Then the call raises GitUnavailable

  Scenario: Rebase still runs against an ancestor and lets git refuse dirty work
    Given a repository "r"
    And "r" commits "root" with a="old"
    And "r" commits "child" with b="new"
    When "r" calls rebase("HEAD~1")
    Then the result's ok is True
    When "r" writes a="dirty"
    And "r" calls rebase("HEAD~1", update_refs=False)
    Then the result's ok is False
    And the command output contains "cannot rebase"

  Scenario Outline: Rebase preserves complete command refusals and propagates spawn failures
    Given a repository "r"
    And "r" commits "root" with a="root"
    And the rebase command of "r" will <outcome>
    When "r" tries rebase("HEAD")
    Then the rebase command outcome is "<outcome>"

    Examples:
      | outcome     |
      | refuse      |
      | fail spawn  |

  Scenario Outline: Command rebase inherits update refs configuration and permits overrides
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
    When "r" calls rebase("main", update_refs=<option>)
    Then the result's ok is True
    And the branch "middle" of "r" rewritten is <rewritten>

    Examples:
      | option | rewritten |
      | None   | True      |
      | True   | True      |
      | False  | False     |

  Scenario: Command rebase reports an already paused rebase without raising
    Given an origin "o"
    And the origin "o" holds a="root\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a="mine\n"
    And the origin "o" advances "main" with a="theirs\n"
    And "r" calls fetch()
    When "r" calls rebase("origin/main")
    Then the result's ok is False
    When "r" calls rebase("origin/main")
    Then the result's ok is False
    And the command output contains "rebase-merge"

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
    Then the result's ok is True

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
    Then the call raises <error>
    When "r" calls branch()
    Then the result is "main"
    When "r" calls snapshot("HEAD")
    Then the result's head is "<mem:before>"

    Examples:
      | operation                                                  | error           |
      | take_branch(branch="topic", base="--orphan", mode="restart") | ValueError      |
      | take_branch(branch="main", base="missing", mode="resume")    | MissingRevision |
      | rebase_onto("--exec=false", squash_message="squash")          | ValueError      |

  Scenario Outline: Other revision consumers reject options before changing the checkout
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "before"
    When "r" tries <operation>
    Then the call raises ValueError
    When "r" calls branch()
    Then the result is "main"
    When "r" calls history(["HEAD"])
    Then the sha of each result entry is ["<mem:before>"]
    When "r" calls refs(["refs/tags/"])
    Then the result is []

    Examples:
      | operation                                                            |
      | checkout("--orphan")                                                 |
      | checkout_new("topic", "-x")                                          |
      | checkout_force("topic", "-x")                                        |
      | reset("--hard")                                                      |
      | merge_ff("--abort")                                                  |
      | cherry("--abbrev=1", "HEAD")                                         |
      | cherry("HEAD", "--abbrev=1")                                         |
      | relate("--all", "HEAD")                                              |
      | relate("HEAD", "--all")                                              |
      | history(["--all"])                                                   |
      | history(["HEAD"], not_on=["--all"])                                   |
      | history(["HEAD"], patch_equivalent_to="--all")                         |
      | tree("--all")                                                        |
      | snapshot("--all")                                                    |
      | dirty("--all")                                                       |
      | landed("--all", "unmatched")                                         |
      | diff("--output=injected", "HEAD")                                     |
      | diff("HEAD", "--output=injected")                                     |
      | tag("probe", "--all")                                                |
      | count(["--all"])                                                     |
      | count(["HEAD"], exclude=["--all"])                                    |
      | add_worktree("<root>/injected", "--orphan")                            |
      | take_branch(branch="--orphan", base="HEAD", mode="resume")            |
      | abort_rebase(restore_to="--hard")                                     |
      | finish_rebase("abort", restore_to="--hard")                           |
      | record("squash", paths="all", mode="squash_to", squash_to="--hard")    |

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

  Scenario: Recording an unresolved conflict is a git failure with hooks enabled
    Given an origin "o"
    And the origin "o" holds a="root\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a="mine\n"
    And the origin "o" advances "main" with a="theirs\n"
    And "r" calls fetch()
    And "r" calls rebase("origin/main")
    When "r" tries record("unresolved", paths="staged", hooks=True, allow_empty=True)
    Then the call raises GitUnavailable
    When "r" calls rebasing()
    Then the result is True
    When "r" calls unmerged()
    Then the result is ["a"]

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
    When "r" tries rebase("missing")
    Then the call raises MissingRevision

  Scenario Outline: Option-like revisions cannot alter history
    Given a repository "r"
    And "r" commits "root" with a="root\n"
    And "r" commits "next" with b="next\n"
    Then "r" rejects option-like revision "<revision>" without changing history

    Examples:
      | revision      |
      | --root        |
      | --abort       |
      | --quit        |
      | --all         |
      | --octopus     |
      | --fork-point  |
      | --independent |
      | -x            |

  Scenario Outline: Option-like revisions leave a paused rebase intact
    Given an origin "o"
    And the origin "o" holds a="root\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a="mine\n"
    And the origin "o" advances "main" with a="theirs\n"
    And "r" calls fetch()
    And "r" calls rebase("origin/main")
    Then the result's ok is False
    And "r" rejects option-like revision "<revision>" without changing history
    When "r" calls rebasing()
    Then the result is True
    When "r" writes a="resolved\n"
    And "r" calls continue_rebase(stage_conflicts=True, check_markers=True)
    Then the result's ok is True
    When "r" calls rebasing()
    Then the result is False

    Examples:
      | revision      |
      | --root        |
      | --abort       |
      | --quit        |
      | --all         |
      | --independent |
      | -x            |

  Scenario: Merge base permits missing revisions and cherry preserves oldest first picks
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "root"
    And "r" commits "first" with b="first"
    And "r" remembers its head as "first"
    And "r" commits "second" with c="second"
    When "r" calls merge_base("missing", "HEAD")
    Then the result is None
    When "r" calls merge_base("HEAD", "missing")
    Then the result is None
    When "r" calls merge_base("<mem:root>", "HEAD")
    Then the result is "<mem:root>"
    When "r" calls cherry("<mem:root>", "HEAD")
    Then the oid of each result entry is ["<mem:first>", "<head:r>"]
    And the upstream of each result entry is [False, False]

  Scenario: Ancestry distinguishes equality ancestors descendants and diverged commits
    Given a repository "r"
    And "r" commits "root" with a="root"
    And "r" remembers its head as "root"
    And "r" commits "left" with b="left"
    And "r" remembers its head as "left"
    When "r" calls is_ancestor("HEAD", "HEAD")
    Then the result is True
    When "r" calls is_ancestor("<mem:root>", "HEAD")
    Then the result is True
    When "r" calls is_ancestor("HEAD", "<mem:root>")
    Then the result is False
    When "r" calls checkout_new("right", "<mem:root>")
    And "r" commits "right" with c="right"
    And "r" calls is_ancestor("<mem:left>", "HEAD")
    Then the result is False

  Scenario Outline: Ancestry reports missing revisions instead of false
    Given a repository "r"
    And "r" commits "root" with a="root"
    When "r" tries is_ancestor(<a>, <b>)
    Then the call raises MissingRevision

    Examples:
      | a         | b         |
      | "missing" | "HEAD"    |
      | "HEAD"    | "missing" |

  Scenario: Ancestry reports an unborn HEAD as a missing revision
    Given a repository "r"
    When "r" tries is_ancestor("HEAD", "HEAD")
    Then the call raises MissingRevision

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
      | is_ancestor("HEAD", "HEAD") |
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
    Then the result's ok is True
    And the remote result carries command output
    When "r" calls delete_remote_at("origin", "refs/heads/pinned", "<mem:root>")
    Then the result's ok is True
    And the remote result carries command output
    When "r" calls delete_remote_at("origin", "refs/heads/pinned", "<mem:root>")
    Then the result's ok is True
    When "r" tries delete_remote_at("origin", "refs/heads/pinned", "<mem:root>", missing_ok=False)
    Then the call raises GitUnavailable

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
    When "r" calls is_ancestor("HEAD", "origin/main")
    Then the result is False

  Scenario: Branch observation faults remain failures
    Given a repository "r"
    And the observations of "r" will fail
    When "r" tries branch()
    Then the call raises GitUnavailable

  Scenario Outline: Revision reads fail when the repository becomes unreadable
    Given a repository "r"
    And "r" commits "root" with a="root"
    And the folder of "r" is deleted behind git's back
    When "r" tries <operation>
    Then the call raises GitReadFailure

    Examples:
      | operation                   |
      | merge_base("HEAD", "HEAD")  |
      | is_ancestor("HEAD", "HEAD") |

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
    Then the result's ok is True
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
    And the failure retains push and verification diagnostics
    When "r" tries delete_remote_at("origin", "refs/heads/main", "<mem:before>", missing_ok=False)
    Then the call raises GitUnavailable

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

  Scenario: A caller supplies the exact object for a push
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" remembers its head as "root"
    And "r" commits "mine" with b="local"
    When "r" calls push("pinned", head="<mem:root>")
    Then the result is a Pushed
    And the result's sha is "<mem:root>"
    And the remote result carries command output
    When "r" calls fetch("origin", refspecs=["refs/heads/pinned"])
    And "r" calls history(["FETCH_HEAD"], limit=1)
    Then the result's 0.sha is "<mem:root>"

  Scenario Outline: Partial push success is distinct from every ref losing a race
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with b="local"
    And the origin "o" advances "main" with c="remote"
    When "r" calls push_refspecs("origin", <refspecs>)
    Then the result is a RemoteRejected
    And the remote result carries command output
    When "r" calls ls_remote("origin", ["new"])
    Then the oid of each result entry is ["<head:r>"]

    Examples:
      | refspecs                                          |
      | ["HEAD:refs/heads/main", "HEAD:refs/heads/new"]       |
      | ["HEAD:refs/heads/new", "HEAD:refs/heads/main"]       |

  Scenario Outline: A pre push hook can refuse without naming itself
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with b="local"
    And "r" has a pre-push hook that <mode>
    When "r" calls <call>
    Then the result is a HookRejected
    And the remote result carries command output

    Examples:
      | mode       | call                                                |
      | error only | push("main")                                        |
      | silent     | push("main")                                        |
      | error only | push_refspecs("origin", ["HEAD:refs/heads/main"])     |
      | silent     | push_refspecs("origin", ["HEAD:refs/heads/main"])     |

  Scenario Outline: A passing pre-push hook followed by a connection drop remains transient
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" has a passing pre-push hook followed by a dropped connection
    When "r" calls <call>
    Then the result is a Transient
    And the remote result carries command output

    Examples:
      | call                                                   |
      | push("main")                                           |
      | push_refspecs("origin", ["HEAD:refs/heads/main"])        |

  Scenario Outline: Push outcomes retain a long hook transcript
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with b="local"
    And "r" has a pre-push hook that verbose refuses
    When "r" calls <call>
    Then the remote result retains both complete output streams

    Examples:
      | call                                                    |
      | push("main")                                            |
      | push_refspecs("origin", ["HEAD:refs/heads/main"])         |
      | push_request("origin", ["HEAD:refs/heads/main"])          |
      | push_lease("origin", "HEAD:refs/heads/main")               |

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

  # shelf-7qsd
  Scenario: Independent clones of one origin have distinct local identities
    Given an origin "o"
    And "r" is a clone of the origin "o"
    And "s" is a clone of the origin "o"
    When "r" remembers identity().key as "key"
    And "s" calls identity()
    Then the result's key is not "<mem:key>"

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
    When "r" calls dirty(ignored_under=["."])
    Then the result's ignored is ["build/a.log", "other/b.log"]
    When "r" calls dirty()
    Then the result's ignored is []

  @real_only
  Scenario: A nested repository in an ignored folder survives an ignored clean and goes with nested (the fake has none)
    Given a repository "r"
    And "r" commits "base" with .gitignore=".venv/\n", a.txt="a\n"
    When "r" writes .venv/lib/x.py="x\n"
    And "r" makes a nested repository ".venv/src/dep" holding f.txt="f\n"
    And "r" calls clean(ignored=True)
    Then the file ".venv/src/dep/f.txt" of "r" holds "f\n"
    And the file ".venv/lib/x.py" of "r" is absent
    When "r" calls dirty(ignored_under=["."])
    Then the result's ignored is [".venv/src/dep/"]
    When "r" calls clean(ignored=True, nested=True)
    Then the file ".venv/src/dep/f.txt" of "r" is absent
    And the file "a.txt" of "r" holds "a\n"
    When "r" calls dirty(ignored_under=["."])
    Then the result's ignored is []
    And the result's untracked is []

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
    Then the result is a RefRejected

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

  Scenario Outline: Fetch retries up to four ref races before succeeding
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" encounters 4 ref races before fetching
    When "r" calls <call>
    Then the result is a <result>

    Examples:
      | call                                       | result        |
      | sync()                                     | Synced        |
      | fetch("origin")                            | CommandResult |
      | fetch("origin", refspecs=["main"])          | CommandResult |

  Scenario: Sync reports offline after five ref races
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" encounters 5 ref races before fetching
    When "r" calls sync()
    Then the result is a Offline
    And the remote result carries command output

  Scenario: Explicit fetch reports the final ref race after five attempts
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" encounters 5 ref races before fetching
    When "r" tries fetch("origin")
    Then the call raises RefRace

  @real_only
  Scenario Outline: A fetch that loses a ref lock succeeds after retrying (the fake has no locks)
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And the origin "o" advances "main" with b.txt="b\n"
    And a competing fetch holds the lock on "origin/main" until the first retry
    When "r" calls <call>
    Then the result is a <result>
    And the remote result carries command output
    And the fetch rested 1 time

    Examples:
      | call            | result        |
      | sync()          | Synced        |
      | fetch("origin") | CommandResult |

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

  # -- squash: one commit in Git objects, never a checkout ---------------------------------------------
  Scenario: A branch squashes onto a moved target as one commit whose parent is the target
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n2\n3\n", b.txt="b\n"
    And "r" calls checkout_new("task")
    And "r" commits "first" with a.txt="one\n2\n3\n"
    And "r" commits "second" with c.txt="c\n"
    And "r" calls checkout("main")
    And "r" commits "moved" with a.txt="1\n2\nthree\n"
    And "r" remembers its head as "target"
    And "r" writes a.txt="edited, not staged\n"
    And "r" stages ["a.txt"]
    And "r" remembers its refs, head and status
    When "r" remembers squash("main", "task", "land the task\n\nbody\n").sha as "s"
    Then the refs, head and status of "r" are unchanged
    When "r" calls history(["<mem:s>"], limit=2)
    Then the subject of each result entry is ["land the task", "moved"]
    And the sha of each result entry is ["<mem:s>", "<mem:target>"]
    When "r" calls tree("<mem:s>")
    Then the tree lists ["a.txt", "b.txt", "c.txt"]
    And the tree reads "a.txt" as "one\n2\nthree\n"
    And the tree reads "c.txt" as "c\n"

  Scenario: The squash's tree id is the tree its commit holds
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    And "r" calls checkout_new("task")
    And "r" commits "work" with b.txt="b\n"
    And "r" remembers snapshot("HEAD").tree as "task_tree"
    And "r" calls checkout("main")
    When "r" calls squash("main", "task", "land")
    Then the result is a Squashed
    And the result's tree is "<mem:task_tree>"

  Scenario: A squash of work already on the target holds the target's tree
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    And "r" calls checkout_new("task")
    And "r" commits "work" with b.txt="b\n"
    And "r" calls checkout("main")
    And "r" commits "landed by hand" with b.txt="b\n"
    And "r" remembers snapshot("HEAD").tree as "main_tree"
    When "r" calls squash("main", "task", "land")
    Then the result is a Squashed
    And the result's tree is "<mem:main_tree>"
    When "r" calls squash("main", "main", "nothing")
    Then the result is a Squashed
    And the result's tree is "<mem:main_tree>"

  Scenario: A conflicting squash names each conflicted path once and makes nothing
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n", b.txt="b\n", "my file"="x\n"
    And "r" calls checkout_new("task")
    And "r" commits "work" with a.txt="task\n", "my file"="task\n", b.txt="b\nmore\n"
    And "r" calls checkout("main")
    And "r" commits "moved" with a.txt="main\n", "my file"="main\n"
    And "r" remembers its refs, head and status
    When "r" calls squash("main", "task", "land")
    Then the result is a Conflicted
    And the result's paths are ["a.txt", "my file"]
    And the refs, head and status of "r" are unchanged

  Scenario: A squash refuses missing and option-like revisions
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    When "r" tries squash("main", "absent", "land")
    Then the call raises MissingRevision
    When "r" tries squash("-x", "main", "land")
    Then the call raises ValueError

  Scenario: A squash runs no hook
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    And "r" calls checkout_new("task")
    And "r" commits "work" with b.txt="b\n"
    And "r" calls checkout("main")
    And "r" has a pre-commit hook that refuses
    When "r" calls squash("main", "task", "land")
    Then the result is a Squashed

  @real_only
  Scenario: A squash is never signed and runs no commit hook (the fake has neither)
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    And "r" has a post-commit hook that refuses
    And "r" config "commit.gpgSign" is "true"
    And "r" config "gpg.program" is "false"
    When "r" calls squash("main", "main", "land")
    Then the result is a Squashed

  @real_only
  Scenario: A squash's author and committer are the configured identity (the fake has no authors)
    Given the machine has no git identity
    And a repository "r"
    And "r" config "user.name" is "Config Author"
    And "r" config "user.email" is "config@example.invalid"
    And "r" commits "root" with a.txt="1\n"
    When "r" remembers squash("main", "main", "land").sha as "s"
    Then the author and committer of "<mem:s>" in "r" are "Config Author <config@example.invalid>"

  @real_only
  Scenario: A squash's author and committer are the injected identity over the config (the fake has no authors)
    Given the repositories commit as "Injected Author"
    And a repository "r"
    And "r" commits "root" with a.txt="1\n"
    When "r" remembers squash("main", "main", "land").sha as "s"
    Then the author and committer of "<mem:s>" in "r" are "Injected Author <injected@example.invalid>"

  Scenario: A squash onto origin's moved tip is on origin only once pushed
    Given an origin "o"
    And the origin "o" holds a="root"
    And "r" is a clone of the origin "o"
    And "r" calls checkout_new("task/x")
    And "r" commits "work" with b="task"
    And the origin "o" advances "main" with c="moved"
    And "r" calls fetch("origin", refspecs=["+refs/heads/main:refs/remotes/origin/main"])
    And "r" remembers history(["origin/main"], limit=1).0.sha as "moved"
    And "r" remembers its refs, head and status
    When "r" remembers squash("origin/main", "task/x", "land").sha as "s"
    Then the refs, head and status of "r" are unchanged
    When "r" calls ls_remote("origin", ["refs/heads/main"])
    Then the oid of each result entry is ["<mem:moved>"]
    When "r" calls history(["<mem:s>"], limit=2)
    Then the sha of each result entry is ["<mem:s>", "<mem:moved>"]
    When "r" calls push_refspecs("origin", ["<mem:s>:refs/heads/main"])
    Then the result is a Pushed
    When "r" calls ls_remote("origin", ["refs/heads/main"])
    Then the oid of each result entry is ["<mem:s>"]

  # -- the push URL ------------------------------------------------------------------------------------
  Scenario: The push URL is the fetch URL when nothing redirects pushes
    Given an origin "o"
    And "r" is a clone of the origin "o"
    When "r" calls remote_url("origin", push=True)
    Then the result is "<mem:origin:o>"
    When "r" tries remote_url("missing", push=True)
    Then the call raises MissingRemote

  Scenario Outline: The push URL follows pushurl, pushInsteadOf and insteadOf
    Given an origin "o"
    And "r" is a clone of the origin "o"
    And "r" config "<key>" is "<value>"
    When "r" calls remote_url("origin")
    Then the result is "<fetch>"
    When "r" calls remote_url("origin", push=True)
    Then the result is "<push>"

    Examples:
      | key                         | value               | fetch           | push               |
      | remote.origin.pushurl       | <root>/elsewhere.git | <mem:origin:o>  | <root>/elsewhere.git |
      | url.pushed/.pushInsteadOf   | <root>/             | <mem:origin:o>  | pushed/o.git       |
      | url.expanded/.insteadOf     | <root>/             | expanded/o.git  | expanded/o.git     |

  Scenario: Every URL of a remote: a push goes to each pushurl, else to each url
    Given an origin "o"
    And "r" is a clone of the origin "o"
    When "r" calls remote_urls("origin")
    Then the result is ["<mem:origin:o>"]
    When "r" calls remote_urls("origin", push=True)
    Then the result is ["<mem:origin:o>"]
    When "r" tries remote_urls("missing", push=True)
    Then the call raises MissingRemote

  Scenario: A second url is listed on both sides; the first stays the one URL
    Given an origin "o"
    And "r" is a clone of the origin "o"
    And "r" config "remote.origin.url" also has "<root>/second.git"
    And "r" config "url.expanded/.insteadOf" is "<root>/second"
    When "r" calls remote_urls("origin")
    Then the result is ["<mem:origin:o>", "expanded/.git"]
    When "r" calls remote_urls("origin", push=True)
    Then the result is ["<mem:origin:o>", "expanded/.git"]
    When "r" calls remote_url("origin", push=True)
    Then the result is "<mem:origin:o>"

  Scenario: Every pushurl is listed on the push side only
    Given an origin "o"
    And "r" is a clone of the origin "o"
    And "r" config "remote.origin.pushurl" is "<root>/a.git"
    And "r" config "remote.origin.pushurl" also has "<root>/b.git"
    When "r" calls remote_urls("origin", push=True)
    Then the result is ["<root>/a.git", "<root>/b.git"]
    When "r" calls remote_urls("origin")
    Then the result is ["<mem:origin:o>"]
    When "r" calls remote_url("origin", push=True)
    Then the result is "<root>/a.git"

  Scenario: An explicit pushurl ignores pushInsteadOf but takes insteadOf
    Given an origin "o"
    And "r" is a clone of the origin "o"
    And "r" config "remote.origin.pushurl" is "<root>/elsewhere.git"
    And "r" config "url.pushed/.pushInsteadOf" is "<root>/"
    When "r" calls remote_url("origin", push=True)
    Then the result is "<root>/elsewhere.git"
    When "r" config "url.expanded/.insteadOf" becomes "<root>/"
    And "r" calls remote_url("origin", push=True)
    Then the result is "expanded/elsewhere.git"

  # -- exclude: ignore rules of one checkout, and park(keep_ignored) ---------------------------------
  Scenario: A checkout's own excludes hide files from that checkout alone
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" adds a worktree "w" at "HEAD" as "w"
    When "w" calls exclude(["/cache/", "*.tmp"])
    And "w" calls exclude(["*.tmp"])
    And "w" writes cache/x="x\n", y.tmp="y\n", z.txt="z\n"
    And "r" writes cache/x="x\n", y.tmp="y\n"
    And "w" calls dirty()
    Then the result's untracked is ["z.txt"]
    When "r" calls dirty()
    Then the result's untracked is ["cache/x", "y.tmp"]

  Scenario: Capture leaves out what the checkout's own excludes hide
    Given a repository "r"
    And "r" commits "one" with a.txt="1\n"
    And "r" calls exclude(["/cache/"])
    And "r" writes cache/x="x\n", new.txt="n\n"
    When "r" remembers the result of capture() as "t"
    And "r" calls tree("<mem:t>")
    Then the tree lists ["a.txt", "new.txt"]

  Scenario: Parking keeps the ignored files, ignored, when the base has other ignore rules
    Given a repository "r"
    And "r" commits "base" with a.txt="1\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" commits "rules" with .gitignore="*.cache\n", b.txt="2\n"
    And "r" writes junk.cache="junk\n", weird[1]*.out="w\n"
    When "r" calls park("<mem:base>", keep_ignored=True)
    Then the result is "<mem:base>"
    And the file "junk.cache" of "r" holds "junk\n"
    When "r" calls dirty()
    Then the result's untracked is ["weird[1]*.out"]
    And the result's tracked is []

  Scenario: Parking with keep_ignored hides the ignored files the base's rules would show
    Given a repository "r"
    And "r" commits "base" with a.txt="1\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" commits "rules" with .gitignore="*.cache\n", b.txt="2\n"
    And "r" writes junk.cache="junk\n"
    When "r" calls park("<mem:base>", keep_ignored=True)
    And "r" calls dirty()
    Then the result's untracked is []
    And the result's tracked is []
    And the file "junk.cache" of "r" holds "junk\n"

  Scenario: Pinned ignored files match literally, not as globs
    Given a repository "r"
    And "r" commits "base" with a.txt="1\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" commits "rules" with .gitignore="*.cache\n"
    And "r" writes we*ird.cache="a\n"
    When "r" calls park("<mem:base>", keep_ignored=True)
    And "r" writes weXird.cache="b\n"
    And "r" calls dirty()
    Then the result's untracked is ["weXird.cache"]

  Scenario: Parking refuses when the base tracks a file that is ignored here
    Given a repository "r"
    And "r" commits "base" with a.txt="1\n", keep.cache="tracked\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" commits "rules" with .gitignore="*.cache\n"
    And "r" removes "keep.cache"
    And "r" stages ["keep.cache"]
    And "r" writes keep.cache="mine\n"
    When "r" tries park("<mem:base>", keep_ignored=True)
    Then the call raises IgnoredFilesWouldBeOverwritten
    And the file "keep.cache" of "r" holds "mine\n"

  # -- capture, commit_tree, update_ref: preserving a checkout's work without touching it -------------
  Scenario: Capture names the final working state and leaves the checkout alone
    Given a repository "r"
    And "r" commits "root" with .gitignore="*.cache\n", a.txt="1\n", b.txt="b\n", c.txt="c\n"
    And "r" writes a.txt="staged\n"
    And "r" stages ["a.txt"]
    And "r" writes a.txt="final\n", new.txt="new\n", junk.cache="junk\n"
    And "r" removes "b.txt"
    And "r" remembers its refs, head and status
    When "r" remembers the result of capture() as "t"
    Then the refs, head and status of "r" are unchanged
    And the index of "r" reads "a.txt" as "staged\n"
    And the file "junk.cache" of "r" holds "junk\n"
    When "r" calls tree("<mem:t>")
    Then the tree lists [".gitignore", "a.txt", "c.txt", "new.txt"]
    And the tree reads "a.txt" as "final\n"
    And the tree reads "new.txt" as "new\n"

  Scenario: An indexed path stays captured when an ignore rule now matches it
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    And "r" writes late.cache="late\n"
    And "r" stages ["late.cache"]
    And "r" writes .gitignore="*.cache\n", other.cache="other\n"
    When "r" remembers the result of capture() as "t"
    And "r" calls tree("<mem:t>")
    Then the tree lists [".gitignore", "a.txt", "late.cache"]

  Scenario: A clean checkout captures its own commit's tree
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    When "r" remembers snapshot("HEAD").head_tree as "head_tree"
    And "r" calls capture()
    Then the result is "<mem:head_tree>"

  Scenario: Capture refuses unresolved merge entries
    Given an origin "o"
    And the origin "o" holds a.txt="1\n"
    And "r" is a clone of the origin "o"
    And "r" commits "mine" with a.txt="mine\n"
    And the origin "o" advances "main" with a.txt="theirs\n"
    And "r" calls sync()
    And "r" calls rebase_onto("origin/main")
    When "r" tries capture()
    Then the call raises UnmergedPaths

  @real_only
  Scenario: Capture refuses a repository nested in the checkout
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    When "r" makes a nested repository "dep" holding f.txt="f\n"
    And "r" tries capture()
    Then the call raises EmbeddedRepositories

  Scenario: Saved work is committed, the index follows it, and the checkout parks clean with its ignored files
    Given a repository "r"
    And "r" commits "base" with a.txt="1\n", b.txt="b\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" writes a.txt="staged\n"
    And "r" stages ["a.txt"]
    And "r" writes a.txt="final\n", new.txt="n\n", keep.log="log\n"
    And "r" removes "b.txt"
    And "r" writes .gitignore="*.log\n"
    And "r" remembers the result of capture() as "t"
    And "r" remembers the result of commit_tree("<mem:t>", ["HEAD"], "wip", when=1700000000) as "wip"
    And "r" calls update_ref("refs/heads/task/x", "<mem:wip>", expected="HEAD")
    When "r" calls reset("<mem:wip>")
    And "r" calls park("<mem:base>", keep_ignored=True)
    And "r" calls dirty()
    Then the result's tracked is []
    And the result's untracked is []
    And the file "a.txt" of "r" holds "1\n"
    And the file "keep.log" of "r" holds "log\n"
    When "r" calls tree("task/x")
    Then the tree reads "a.txt" as "final\n"

  Scenario: A detached checkout parks clean after the same save
    Given a repository "r"
    And "r" commits "base" with a.txt="1\n"
    And "r" remembers its head as "base"
    And "r" calls take_branch("task/x", "HEAD", mode="resume")
    And "r" calls park("<mem:base>")
    And "r" writes a.txt="mine\n", new.txt="n\n"
    And "r" remembers the result of capture() as "t"
    And "r" remembers the result of commit_tree("<mem:t>", ["task/x"], "wip", when=1700000000) as "wip"
    And "r" calls update_ref("refs/heads/task/x", "<mem:wip>", expected="task/x")
    When "r" calls reset("<mem:wip>")
    And "r" calls park("<mem:base>", keep_ignored=True)
    And "r" calls dirty()
    Then the result's tracked is []
    And the result's untracked is []
    And the file "a.txt" of "r" holds "1\n"

  Scenario: A commit of a captured tree takes exactly the parents given, and names no ref
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    And "r" remembers its head as "root"
    And "r" calls checkout_new("side")
    And "r" commits "side" with s.txt="s\n"
    And "r" remembers its head as "side"
    And "r" calls checkout("main")
    And "r" writes w.txt="w\n"
    And "r" remembers the result of capture() as "t"
    And "r" remembers its refs, head and status
    When "r" remembers the result of commit_tree("<mem:t>", ["<mem:root>", "<mem:side>"], "wip\n\nbody\n") as "wip"
    Then the refs, head and status of "r" are unchanged
    When "r" calls is_ancestor("<mem:side>", "<mem:wip>")
    Then the result is True
    When "r" calls is_ancestor("<mem:root>", "<mem:wip>")
    Then the result is True
    When "r" calls history(["<mem:wip>^"], limit=1)
    Then the subject of each result entry is ["root"]
    When "r" calls tree("<mem:wip>")
    Then the tree lists ["a.txt", "w.txt"]

  Scenario: The same tree, parents, message and time make the same commit
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    And "r" remembers its head as "root"
    And "r" writes w.txt="w\n"
    And "r" remembers the result of capture() as "t"
    When "r" remembers the result of commit_tree("<mem:t>", ["<mem:root>"], "wip", when=1700000000) as "one"
    And "r" calls commit_tree("<mem:t>", ["<mem:root>"], "wip", when=1700000000)
    Then the result is "<mem:one>"
    When "r" remembers the result of commit_tree("<mem:t>", [], "root-less", when=1700000000) as "free"
    And "r" calls history(["<mem:free>"], limit=2)
    Then the subject of each result entry is ["root-less"]

  Scenario: A commit of a missing tree or parent is refused
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    When "r" tries commit_tree("0123456789012345678901234567890123456789", [], "x")
    Then the call raises MissingRevision

  Scenario: A ref moves only from its expected value
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    And "r" remembers its head as "root"
    And "r" commits "next" with a.txt="2\n"
    And "r" remembers its head as "next"
    When "r" calls update_ref("refs/heads/wip", "<mem:root>", expected=None)
    Then the result is a RefUpdated
    And the result's sha is "<mem:root>"
    When "r" calls update_ref("refs/heads/wip", "<mem:next>", expected=None)
    Then the result is a RefMoved
    And the result's actual is "<mem:root>"
    When "r" calls update_ref("refs/heads/wip", "<mem:next>", expected="<mem:next>")
    Then the result is a RefMoved
    And the result's actual is "<mem:root>"
    When "r" calls update_ref("refs/heads/wip", "<mem:next>", expected="<mem:root>")
    Then the result is a RefUpdated
    When "r" calls refs(["refs/heads/wip"])
    Then the result's 0.sha is "<mem:next>"

  Scenario: A ref that is missing is a move away from an expected value
    Given a repository "r"
    And "r" commits "root" with a.txt="1\n"
    When "r" calls update_ref("refs/heads/gone", "HEAD", expected="HEAD")
    Then the result is a RefMoved
    And the result's actual is None

  Scenario: A checkout on the branch catches up to a moved ref without losing its files
    Given a repository "r"
    And "r" commits "root" with .gitignore="*.cache\n", a.txt="1\n"
    And "r" writes a.txt="work\n", new.txt="new\n", junk.cache="junk\n"
    And "r" remembers its head as "root"
    And "r" remembers the result of capture() as "t"
    And "r" remembers the result of commit_tree("<mem:t>", ["<mem:root>"], "wip") as "wip"
    When "r" calls update_ref("refs/heads/main", "<mem:wip>", expected="<mem:root>")
    And "r" calls reset("<mem:wip>")
    And "r" calls dirty()
    Then the result's tracked is []
    And the result's untracked is []
    And the file "a.txt" of "r" holds "work\n"
    And the file "junk.cache" of "r" holds "junk\n"
