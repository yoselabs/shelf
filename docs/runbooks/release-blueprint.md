# Release blueprint

Before the tag, never after. Blueprint changes the verdict of every repository that adopts it.

1. `just check-all` green on main's tip.
2. `python3 -I tools/corpus_diff.py` (base: the newest `blueprint-v*` tag, head: the working tree). It prints only the rows whose verdict
   moved, per repository of `tools/corpus.toml`. Read every `passing -> failing`: each one is either a real gap the release now reports
   (say so in the CHANGELOG) or a false positive (fix the row first). A new row warns until the next audit (ADR 0018); one that fails
   here as a hard fail is a bug.
3. Version files: `packages/blueprint/pyproject.toml`, `catalog/blueprint.toml` (`release`), `catalog/README.md` (`python tools/catalog.py`),
   `uv.lock` (`uv lock`), and the CHANGELOG heading (`## Unreleased` becomes `## X.Y.Z`).
4. PR, merge, then the annotated tag `blueprint-vX.Y.Z` on the merge commit, pushed. The pre-push tag check
   (`tools/tag_check.py`) fails if a tag holds another version than its name. Old tags are never moved or deleted.
5. Adoption by repositories is a separate step, with the diff from 2 as its list.
