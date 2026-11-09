# Signal-handler output

The parent sees `ready` as soon as the child's flush writes to the pipe; the child
can still hold its buffered-writer lock. SIGTERM then runs a handler that calls
`print`, recursively acquiring that lock. Python raises RuntimeError and exits 1;
the CLI correctly returns that code.

Use `os.write(1, b"got term\n")` in the test child's handler so it bypasses the
buffered writer. Keep `sys.exit(7)`, the parent-to-wrapper SIGTERM, and the receipt
assertion. Drain both pipes with the existing finite wait budget and attach both
outputs to an exit-code failure. Also assert empty stderr and the released lease.
No retries, skip, timeout increase or expected-value weakening is added to the test.
