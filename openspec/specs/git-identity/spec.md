## Requirements

### Requirement: Local identity follows the canonical common directory

`Repo.identity()` SHALL derive its key and common directory from the canonical local Git common directory. Linked worktrees and symlinked entry paths into that directory SHALL share the key. Independent clones SHALL remain distinct even with the same origin.

#### Scenario: Linked and symlinked paths name one local repository

- WHEN identity is observed from a checkout, its linked worktree and its symlinked path
- THEN all observations have the same canonical common directory and key
- AND a symlinked common metadata directory is resolved before identity derivation

#### Scenario: Clones of one remote are distinct

- WHEN two independent local clones share an origin
- THEN their identity keys differ

### Requirement: Optional origin is distinct from failed observation

The origin SHALL NOT influence the local key. Only a verified missing origin SHALL produce `origin_url = None`; other remote read failures SHALL propagate as `GitReadFailure`. Existing discovery failures remain fail-loud.

#### Scenario: Origin changes with fresh observations

- WHEN origin is absent, added, then changed with memoization disabled
- THEN current optional origin metadata is returned and the local key is unchanged

#### Scenario: Origin cannot be observed

- WHEN remote reading fails or returns empty success output
- THEN identity raises a read failure rather than reporting absent origin

### Requirement: Discovery recognizes filesystem-boundary absence

A known Git exit-128 diagnostic stating no repository was found up to a mount point SHALL raise `NotARepo`. Unknown faults, malformed diagnostics and other exit codes SHALL remain `GitUnavailable`. Classification belongs to the existing Git error owner.

#### Scenario: Discovery stops at a filesystem boundary

- WHEN Git exits 128 with its mount-point repository absence diagnostic
- THEN the library raises `NotARepo`, including when the boundary explanation follows

#### Scenario: Repository reading is unavailable

- WHEN Git reports a permission failure, malformed absence diagnostic or unexpected exit code
- THEN the library retains `GitUnavailable`
