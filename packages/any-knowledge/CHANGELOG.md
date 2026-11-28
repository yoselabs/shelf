# any-knowledge — changelog

AI-facing only: one line per contract-shape change, arrow notation.

## 0.2.0

- `agents/testing.md` template: the slow-test section says what `docs/agents/testing.md` says (a second `-m slow` pass for a suite whose key changed), no longer "the per-commit run leaves it out" (shelf-q40b).

- 0.1.0: moved out of blueprint: `adr` (FOLDER, files, parse, problems, index), `templates` (`Selection`, required, block, render, install), `checks` (glossary, adr_format, adr_index -> list[str]); verbs `index [--write]`, `check [--glossary]`, `seed`.
