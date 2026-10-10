<!-- blueprint:begin -->
## Working agreement (managed by blueprint; do not edit between the markers)

Done = `make check` green over the whole repo. Never `--no-verify`. Commit only on the owner's yes.
Read a file below when its trigger applies, not before.

| file | read when |
|---|---|
| [docs/agents/constitution.md](docs/agents/constitution.md) | before changing anything: how work is done here |
| [docs/agents/working-with-agents.md](docs/agents/working-with-agents.md) | at session start and handoff: loop, rules, survey |
| [docs/agents/gate.md](docs/agents/gate.md) | when a check fails, or you add one or touch hooks or CI |
| [docs/agents/testing.md](docs/agents/testing.md) | before writing or changing any test |
| [docs/agents/architecture.md](docs/agents/architecture.md) | before adding a module, dependency or layer |
| [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md) | before creating, claiming or closing work (`bd`) |
| [docs/agents/domain.md](docs/agents/domain.md) | before naming a concept or recording a decision; index: `docs/adr/INDEX.md` |
{{stack_rows}}

Run `/blueprint` to audit this repo's setup; it changes nothing until the owner says yes.
<!-- blueprint:end -->
