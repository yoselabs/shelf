1. Manifest as data: `plugins/*.toml` for the table in design.md, a `plugin` field on each row derived from its module, a test that every
   registered row has exactly one plugin. `check --list` shows it. Audit verdicts of shelf and a2kay unchanged.
2. Default states and the switch: `[plugins]` table in `blueprint.toml` (`beads = false`); resolution order; dependents off with a notice;
   an `off` plugin is not asked until opted in. Scenarios from shelf-ysmh.
3. Architecture test: a plugin imports another only through `requires` (`just arch`).
4. Split the straddling rows (`gate.git-remote`, `secrets.scanner`, `gate.hooks-recipe`).
5. Move code, one plugin per change: beads first (most of the rows, the owner's trigger), then mise, then the rest.
6. Third-party plugin load path, once the open questions are answered by a real second plugin author.
