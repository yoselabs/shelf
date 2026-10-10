# The gate

One command decides done. Humans, agents, hooks and CI all call the same one.

| item | value |
|---|---|
| Command | `make check` |
| Runs | format check, lint, types, spelling, dependency hygiene, tests with coverage, architecture rules, `make blueprint` (the stack list is in the stack file) |
| Passes when | exit 0 over the whole repo (never only touched files), nothing skipped |

## Never bypass

| forbidden | do instead |
|---|---|
| `git commit --no-verify`, `git push --no-verify`, `SKIP=<hook>` | Fix the failure. If the check is wrong, change the check in its own reviewed commit |
| Deleting or weakening a test to go green | Fix the code; a test goes only with proof it guards nothing |
| Inline suppression | One scoped config line with a reason |
| "It fails on main too" | Still not done: fix it, or open a bead and tell the owner |

Why: a gate that can be waved through is not a gate. Only the owner may bypass.
## Hooks

prek owns the hooks, from `.pre-commit-config.yaml`. bd never installs its own (`bd init --skip-hooks`;
`bd hooks install` is never run): bd's hooks injected beside another manager's silently stop blocking commits.

| stage | runs | why here |
|---|---|---|
| pre-commit | `bd hooks run pre-commit`, then the stack's fast checks on staged files | Fast: seconds |
| prepare-commit-msg, post-merge, post-checkout | `bd hooks run <event>` | bd keeps its data in step |
| pre-push | `bd hooks run pre-push`, `bd dolt push` (non-fatal), then `make check` | Heavy checks once per push |

Install after clone: `prek install`. Recipe: blueprint's `recipes/pre-commit-config.yaml`; bd hooks come first.

## CI

CI runs `make check` and nothing else of its own. A CI step missing from `make check` is a gate gap: move it in.

## Adding a check

Plant a violation, see the gate fail, add the check to `make check` (a hook only if it takes seconds), remove the violation, see green.
