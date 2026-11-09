# Process-lock acquisition failure

## ADDED Requirements

### Requirement: An unregistered descriptor has one acquisition owner
Public acquire MUST close its descriptor on every refused or failing path before
the existing registry takes ownership. Errors MUST propagate without leaving an
inaccessible kernel lock.

#### Scenario: Failure after flock succeeds
- WHEN metadata serialization, native write/truncate, registry construction or interruption fails acquisition
- THEN the caller receives that failure without a lock handle
- AND a real independent contender can acquire the path
- AND the failed descriptor is closed and the registry has no entry for it.

#### Scenario: Reading a refused holder fails
- WHEN an actual foreign holder owns the lock and its metadata observation raises
- THEN the temporary acquisition descriptor is closed and the error propagates
- AND the live holder stays exclusive until it releases its lock.

### Requirement: Existing successful ownership is unchanged
Successful process/thread exclusion, reentrancy and last-reference release MUST
retain the existing contract without a new public API or inheritance behavior.

#### Scenario: Successful nested handles
- WHEN one process acquires the same path reentrantly
- THEN another process remains refused until the last matching handle releases.
