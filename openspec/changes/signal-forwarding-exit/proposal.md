# Stabilize the lease signal-forwarding scenario

Owner: any-lease. Task: shelf-iz00.

The integrated gate observed the CLI exit with 1 where the child fixture promised
7. Capture the failing child's stderr before deciding whether production signal
forwarding needs repair. Preserve real SIGTERM propagation, the child's exit code,
the receipt marker, finite waits and lease release.

The captured failure identifies buffered stdout reentrancy inside the test child.
Only the scenario fixture changes; production CLI and lease ownership remain as-is.
