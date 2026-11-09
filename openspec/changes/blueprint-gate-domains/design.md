# Domain ownership

`concerns/gate.py` owns explicit ordered checkpoint registration. Domain modules
own execution and evidence without registering at import time; importing workflow
discovery through facts cannot partially register or reorder checkpoints.

| Module | Owns |
| --- | --- |
| gate_command | Gate discovery, dry run, runner migration |
| gate_ci | Workflow discovery, existing step parser, manifest checks, Actions results |
| gate_hooks | Versioned hook ownership and installed hooks |
| gate_guards | Reachable hook commands, scripts, red-test coverage, checker wiring |
| gate_clone | Clone setup, LFS hydration, timed gate, working-tree snapshot |
| gate_git | Default branch, remote, clone config, unmerged-branch policy |
| gate_lfs | LFS declaration, pointer validation, filter installation |

Facts calls workflow discovery from gate_ci. Runner uses branch policy from gate_git.
The clone clock test patches gate_clone. Shared LFS declaration/install advice is
owned by gate_lfs. No parser or helper is copied; no old import path is reexported.

The check decorator derives concern from the explicit ID, never the callable's
module. Ordered registration preserves the runner's evaluation and report order.
