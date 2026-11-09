# Registered process start

## Requirements

### Requirement: Register before target exec
The owning process API MUST obtain complete boot-aware identity and finish the
injected registration operation before allowing target execution in that process.

#### Scenario: Durable registration is blocked
- WHEN the registration callback has not returned
- THEN target code cannot write its marker or consume prompt stdin
- AND callback failure or controller EOF exits without target exec.

#### Scenario: Signal interrupts registration
- WHEN a held SIGTERM/SIGINT handler or callback raises BaseException
- THEN cleanup retains the freshly owned process and propagates the interruption
- AND no target execution is permitted.

### Requirement: Preserve target semantics
The registered target MUST inherit exact supplied argv/environment/cwd and original
stdio, retaining its registered PID/session, without private control FD leakage.
Startup failures MUST be explicit native errors, never parsed display output.

#### Scenario: Shell-looking argument and Python environment
- WHEN argv contains shell syntax and environment includes Python startup settings
- THEN argv remains literal and user startup cannot run before permission
- AND the exec target receives the original environment.

### Requirement: Unknown identity cannot authorize execution
Native observation MUST distinguish absent/different identity from unavailable
observation and retain boot identity across process observation.

#### Scenario: Native process observation fails
- WHEN identity is unreadable, malformed or lacks boot identity
- THEN registration cannot permit target exec
- AND unknown is not reported as known absence.
