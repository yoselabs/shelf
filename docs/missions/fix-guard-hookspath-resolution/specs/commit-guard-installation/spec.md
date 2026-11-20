## ADDED Requirements

### Requirement: The guard is installed where git actually looks for hooks
`tools/hooks/install.py` SHALL resolve the hook directory with `git rev-parse --git-path hooks`,
which honors `core.hooksPath`. It SHALL NOT derive the hook directory by appending `hooks` to the
git directory.

#### Scenario: A repo sets core.hooksPath (beads, husky, lefthook, pre-commit)

- **WHEN** the installer runs in a repo where `core.hooksPath` points somewhere other than
  `.git/hooks`
- **THEN** the guard is written into the directory `core.hooksPath` names — the one git will
  execute — and not into `.git/hooks`

#### Scenario: A repo has no core.hooksPath set

- **WHEN** the installer runs in a repo with `core.hooksPath` unset
- **THEN** the guard is written to `.git/hooks/pre-commit`, unchanged from prior behavior

### Requirement: A successful install means the guard was observed to block

The installer SHALL confirm the guard's effect by executing the resolved hook against a seeded
offending state and requiring a non-zero exit. It SHALL NOT report success on the basis of a file
having been written, a marker being present, or a mode bit being set.

#### Scenario: The written hook does not actually fire

- **WHEN** the guard is written successfully but the resolved hook does not block an offending
  state
- **THEN** the installer exits non-zero and reports the guard as **not live**, naming the
  directory it wrote to and the directory git will read

#### Scenario: Verification cannot be performed

- **WHEN** verification cannot run — for example the guard script is absent because the shelf is
  not cloned, which `HOOK` treats as a deliberate fail-open
- **THEN** the installer reports **unverified**, distinctly from verified, with its own exit code
  — "could not check" is never reported as "checked"

#### Scenario: Verification leaves the repo untouched

- **WHEN** verification runs in a repo with unrelated uncommitted changes
- **THEN** the index, tracked files, and commit history are byte-identical afterwards; the
  installer performs no `git reset --hard`, `git stash`, or commit

### Requirement: A foreign hook's owner is named, and the guard is never silently chained

When the resolved hook exists and is not shelf-managed, the installer SHALL refuse, SHALL identify
the managing tool by its marker where recognizable, and SHALL state that tool's own extension
point. It SHALL NOT append the guard into a hook owned by another tool.

#### Scenario: The resolved hook is beads-managed

- **WHEN** the existing hook carries a `BEGIN BEADS INTEGRATION` marker
- **THEN** the installer refuses, names beads, and directs the operator to append **after** the
  `END` marker — not inside the managed block, which a `bd` upgrade would clobber

#### Scenario: The resolved hook belongs to the pre-commit framework

- **WHEN** the existing hook is the pre-commit framework's
- **THEN** the installer refuses and states that the guard is already supported there via
  `.pre-commit-config.yaml` (`no-local-shelf-source`), so no manual chaining is required

#### Scenario: Both the pre-commit framework and beads want the hook slot

- **WHEN** the repo carries a `.pre-commit-config.yaml` **and** `core.hooksPath` is set to a
  beads-managed directory — a configuration where only one of the two tools can be live
- **THEN** the installer names which tool currently owns the slot, and warns that
  `git config --unset-all core.hooksPath` (the hint pre-commit itself prints) would revive
  pre-commit while silently disabling every beads hook, including the `bd dolt push` chain
- **AND** it does not choose between them — arbitrating hook ownership is the repo's call,
  not the installer's

#### Scenario: The resolved hook is hand-written or unrecognized

- **WHEN** the existing hook matches no known manager's marker
- **THEN** the installer refuses with the existing generic advice, unchanged

## MODIFIED Requirements

### Requirement: Onboarding states what the installer's success does and does not cover

`docs/consuming-the-shelf.md` §2 SHALL state that the installer's success signal means the guard
was observed to block, and SHALL state that clones which installed the guard before this change
remain unguarded until the installer is re-run.

#### Scenario: An operator onboards a clone that already ran the old installer

- **WHEN** an operator reads §2 in a clone whose guard was installed before this change
- **THEN** the document tells them the prior install may be silently dead and that re-running the
  installer is the only remedy — no change to this repo can repair another clone

#### Scenario: A reader relies on "hooks cannot be committed"

- **WHEN** a reader reaches §2's premise that git hooks are per-clone and cannot be committed
- **THEN** the document notes the exception: hooks under an in-tree `core.hooksPath` (such as
  beads' `.beads/hooks`, which `bd init` commits) are tracked and do travel with a clone
