"""any-proc — child processes a program starts and owns.

Four modules, one concern each:

- :mod:`any_proc.run` — run a child once: JSON arguments on stdin under a size cap, OS
  resource limits, a timeout, and one marked JSON result line read back. Both ends of the
  marker live here.
- :mod:`any_proc.supervise` — keep one long-lived child alive: spawn, probe, start
  timeout, graceful stop, a restart budget over a rolling window with capped backoff, and
  log rotation between runs.
- :mod:`any_proc.cpus` — the CPUs this process may really use: host affinity (or the core
  count) capped by a container's cgroup quota. A host fact, not about child processes.
- :mod:`any_proc.testing` — test children that must not outlive the test process: a child in a process group of its own and
  a detached watcher that kills the group when the test process dies by SIGKILL.

Stdlib plus ``stream-proc``. Import the module you need; nothing is re-exported here, so
``any_proc.run`` stays the module and never a function shadowing it.
"""
