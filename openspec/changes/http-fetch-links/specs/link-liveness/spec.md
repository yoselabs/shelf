# Link liveness

## ADDED Requirements

### Requirement: Public hosts only
The checker SHALL validate the initial host and every bounded redirect, refuse any nonpublic DNS answer, and pin the validated IP for connection.

#### Scenario: DNS rebinding
- WHEN a hostname is validated as public
- THEN the opener receives that validated IP and an unexpected private peer is refused

### Requirement: Bounded checking
The checker SHALL apply per-hop timeouts, HEAD/GET fallback, bounded batch concurrency and an overall deadline.

#### Scenario: Deadline
- WHEN a batch deadline expires
- THEN unfinished URLs are unknown and all workers are cancelled and awaited
