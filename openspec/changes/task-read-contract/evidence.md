# Verification

Before source changes, focused public read scenarios reproduced 35 failures:
wrong-typed consumed text, malformed dependencies, an empty show response,
multiple show rows and mismatched identity. Log: `/tmp/shelf-ryf2-before.log`.
The protocol/fake contract test first failed on the absent exported protocol:
`/tmp/shelf-ryf2-contract-before.log`.

The required absence-classifier follow-up reproduced 12 more failures covering
backend/database/table errors and mixed diagnostics at both the owning classifier
and public read surface: `/tmp/shelf-ryf2-classify-before.log`.
The existing recorded not_found fixture and Issue <id> not found classifier case
remain acceptance evidence; no database writes or new live backend fixtures were needed.

The completed package tests cover the shared real/fake read contract, independent
backlogs, raw-text preservation, omitted defaults, dependency aliases and arbitrary
nonempty relationship values, typed read faults and transport argv. Existing write
and boundary suites remain part of the focused package run. Production and test
paths are passed explicitly to strict typechecking. Focused package run: 113 passed; explicit production and test typecheck: zero errors.
Lint, formatting, spelling, dependency hygiene and unchanged size caps are checked
before freeze. Full integrated gates and release belong to the coordinator.
