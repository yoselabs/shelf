# Implementation and validation

Tests first: public-host, redirect, fallback, deadline and rebinding scenarios observed red before implementation. Implementation, documented exports and 0.4.0 release metadata added.

61 package and catalog-release tests pass, including transport pinning, caller/worker cancellation and DNS child cleanup. Repo-wide guard, preset, blueprint, lint, strict types, architecture, spelling and dependency checks pass using the existing offline shelf environment and this checkout’s package sources.

Validation remains incomplete: `uv run just check` stops at `beads-lint` because this checkout has no answering Beads database. The supplementary affected run selected 4,781 cases, reported failures and stalled at 93%; interrupted after several minutes. No database bootstrap, consumer edits, network access, commits, checkout or push authorized or performed.
