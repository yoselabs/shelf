# Layering tools for the node, go and rust profiles

Date 2026-11-20 (mission blueprint-multi-stack-contracts, task 4; bead shelf-jc7r.4). Method: ONE pass of web searches, read as
search-result summaries and the pages they name; nothing was installed or run (D = documented, J = judgement). So all three profiles ship
`status = "provisional"`: the first consumer that runs one red and green promotes it (as dotnet.toml's header says for its roles).
Rule (design D4): every profile has an `architecture` role that is not `na`; the layering tool fails the gate on a forbidden edge.

| Stack | Tool | Evidence (URL, read 2026-11-20) | What it enforces | Verdict |
|---|---|---|---|---|
| node | dependency-cruiser | https://github.com/sverweij/dependency-cruiser ; https://raw.githubusercontent.com/sverweij/dependency-cruiser/HEAD/doc/rules-reference.md (D: `forbidden`, `allowed`, `required` rules over the resolved module graph; cycles; runs as a CLI) | forbidden edges between folders and workspace packages, circular dependencies, orphan modules; one config `.dependency-cruiser.cjs`; `depcruise` exits non-zero on an error-severity rule | ✅ chosen |
| node | eslint-plugin-boundaries | https://github.com/javierbrea/eslint-plugin-boundaries (D: elements = folders, `boundaries/dependencies` rule; editor feedback) | folder-level layering inside the lint run | alternative only: no graph-wide checks (cycles), tied to ESLint; the profile's linter is Biome, so a second linter would be needed |
| node | eslint-plugin-dependency-cruiser | https://github.com/pekala/eslint-plugin-dependency-cruiser (D: wrapper; search summary calls it slow) | the same rules in the editor | ❌ not adopted (slow, a second runner) |
| go | go-arch-lint | https://pkg.go.dev/github.com/fe3dback/go-arch-lint ; https://hub.docker.com/r/fe3dback/go-arch-lint (D: `.go-arch-lint.yml` components with `canUse` lists, MIT, release v1.14.0 seen in a guide, `check` and `graph` commands) | layers as components, who may import whom, vendor allow-lists | ✅ chosen |
| go | depguard (inside golangci-lint) | search results: golangci-lint bundles depguard for allow/deny import lists; no authoritative comparison found (J) | per-package import allow/deny lists | supplement: the linter role's golangci-lint config may switch it on for third-party bans; it is not the layering tool |
| go | the `internal/` directory rule | Go language rule (D: go.dev/doc/go1.4#internalpackages) | visibility between module trees only | not enough alone: says nothing about layers inside one module |
| rust | workspace crates as layers + cargo-deny `[bans]` with `wrappers` | https://embarkstudios.github.io/cargo-deny/checks/bans/cfg.html (D: `deny = [{ crate = "x", wrappers = ["only-this-may-use-it"] }]`, `wildcards`); worked example https://github.com/torrust/torrust-tracker/pull/1932 (core may not depend on server: seen flagged as a banned error; internal path dependencies need explicit versions to avoid wildcard-ban failures) | a lower-layer crate may be depended on by named crates only; cargo itself already refuses cycles between crates | ✅ chosen, with the limit that `wrappers` judge direct dependencies only |
| rust | cargo-modules / cargo-depgraph | not read beyond name (J) | graphs, not enforcement | ❌ no failing exit |

## Choices the roles around the layering tool make (J, no hands-on)

Not researched with the same care as architecture; they are the common current defaults and carry `provisional` until a consumer runs them.

- node: pnpm or npm with a committed lockfile and `engines`/`packageManager`; Biome (format + lint, one binary); `tsc --noEmit` strict; knip for
  unused and missing dependencies; vitest with `coverage.thresholds`; typos.
- go: `go.mod` with `go` and `toolchain` directives, `go.sum`, `go mod verify`; gofumpt via golangci-lint v2 formatters; golangci-lint v2;
  `go vet`; `go mod tidy -diff` plus govulncheck; `go test -race`; go-test-coverage (`.testcoverage.yml` thresholds); typos.
- rust: `rust-toolchain.toml` + committed `Cargo.lock` with `--locked`; `cargo fmt --check`; `cargo clippy -- -D warnings` with `[workspace.lints]`;
  rustc as the type checker with `unsafe_code = "forbid"`; cargo-deny (advisories, licenses, bans) and cargo-machete; `cargo test`/nextest;
  cargo-llvm-cov `--fail-under-lines`; typos.

## Not covered

No tool was run; versions are not pinned in the profiles for that reason (a pin needs a release date read from the registry).
Mixed repos (node beside python) are task 5.
