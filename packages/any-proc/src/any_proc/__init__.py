"""any-proc — child processes a program starts and owns.

Two modules, one concern each:

- :mod:`any_proc.run` — run a child once: JSON arguments on stdin under a size cap, OS
  resource limits, a timeout, and one marked JSON result line read back. Both ends of the
  marker live here.
- :mod:`any_proc.supervise` — keep one long-lived child alive: spawn, probe, start
  timeout, graceful stop, a restart budget over a rolling window with capped backoff, and
  log rotation between runs.

Stdlib only. Import the module you need; nothing is re-exported here, so
``any_proc.run`` stays the module and never a function shadowing it.
"""
