# Health signals

Read before planning. The system is healthy when these trend the right way. A bad trend is a defect in slicing or in the system, never noise; the only accepted excuse is `phase = "early"`, and even then the trend must turn within weeks. The task-loop dashboard and run retro compute them (weekly); an agent never computes them by hand. `{{hot_files}}` names this repo's shared hot files; `{{core}}` its Core folder.

| signal | healthy trend | a bad trend means | planner action |
|---|---|---|---|
| Core churn: share of beads touching `{{core}}` | falling | slicing is bad or the Core contract is wrong | plan the contract fix as its own bead first |
| single-feature beads: share touching one feature folder only | rising | features reach into each other or into shared files | file the split of the shared file or contract |
| hot-file edits per bead (`{{hot_files}}`) | falling | a shared file needs a per-feature split | file the split bead |
| first-pass landing: beads landed with 1 stage and no send-back | rising | beads too big or plans vague | split smaller; sharpen the scenarios |
| affected-test narrowing: share of tests safely skipped | rising | the dependency graph is too coupled | decouple the modules |
| gate red after the writer's checks were green | about 0 | the writer's checks miss a gate step | move that step into the writer's checks |
| replans and asks per bead | falling | scenarios or docs miss facts | add the fact to the right doc |
| tokens per landed bead | falling | context waste, rereads, oversized beads | read the run retro |
