# Evidence

The original unmodified scenario was exercised with captured stdout/stderr.
An initial 400 probes at concurrency 4 passed; a loaded run at concurrency 16
captured 359 instances of the original exit-1 failure before a separate
15-second probe timeout ended result collection. The first captured traceback:

```text
Traceback (most recent call last):
  File "<string>", line 3, in <module>
  File "<string>", line 2, in <lambda>
RuntimeError: reentrant call inside <_io.BufferedWriter name='<stdout>'>
```

Full diagnostic output: `/tmp/shelf-iz00-reproduce-loaded.log`. The synthetic
held-flush probe passed; it is not evidence of deterministic reproduction.
The observed original-scenario traceback establishes the cause directly.

The timeout path killed and waited for its confirmed owned wrapper. A subsequent
read-only process-table scan using the exact diagnostic child command and unique
wrapper root arguments found no remaining original diagnostic wrappers or children.
No process was selected or killed by name. The corrected probe additionally owns
an isolated process group and bounded cleanup for readiness/exit failure.

After the fixture repair:

| Check | Result |
| --- | --- |
| Original signal scenario with repaired handler, concurrency 16 | 256 probes: exit 7, receipt marker, no stderr |
| Entire any-lease package test suite | 37 passed in 2.80s |
| Explicit any-lease production typecheck | Zero errors |
| Lint, formatting and unchanged size caps | Passed |

Verification logs: `/tmp/shelf-iz00-fixed-stress.log`,
`/tmp/shelf-iz00-focused-tests.log`, `/tmp/shelf-iz00-types.log`.
Full integrated gates and native Mac validation remain the coordinator's work.
