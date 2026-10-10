# Culture templates

Files blueprint copies into a consumer repo. `{{name}}` marks what the agent fills from the repo;
everything else is fixed text. Edit here, never in a consumer's copy of an unmodified file.

| template | target in the consumer | required |
|---|---|---|
| `agents/constitution.md` | `docs/agents/constitution.md` | always |
| `agents/working-with-agents.md` | `docs/agents/working-with-agents.md` | always |
| `agents/gate.md` | `docs/agents/gate.md` | always |
| `agents/testing.md` | `docs/agents/testing.md` | always (fill `scenario_dir`, `unit_dir`, `architecture_dir`) |
| `agents/architecture.md` | `docs/agents/architecture.md` | always (fill `layers`, `layer_config`) |
| `agents/issue-tracker.md` | `docs/agents/issue-tracker.md` | always while the tracker is beads |
| `agents/domain.md` | `docs/agents/domain.md` | always |
| `agents/python.md` | `docs/agents/python.md` | per stack: python-uv |
| `agents/dotnet.md` | `docs/agents/dotnet.md` | per stack: dotnet |
| `agents/godot.md` | `docs/agents/godot.md` | per framework: godot (fill `godot_root`) |
| `agents-md-block.md` | the managed block in `AGENTS.md`, between its markers | always (fill `stack_rows`: one table row per stack or framework file present) |
