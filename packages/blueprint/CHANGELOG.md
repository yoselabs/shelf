# blueprint — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.2.0: `report.write(run, repo, today, prune=)` ⇒ `report.write(run, repo, today)` plus `report.prune_stale(repo, written)` (the CLI calls it after a full run, not after `--concern`); `blueprint.testing` `Repo.write(rel, text, executable=)` ⇒ `Repo.write(rel, text)` and `Repo.write_executable(rel, text)`; no bool mode parameters (Article III)
