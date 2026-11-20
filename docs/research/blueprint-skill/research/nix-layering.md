# A layering tool for Nix

Date 2026-11-20 (follow-up to node-go-rust-layering.md; bead shelf-jc7r.4). Method: two web searches (one extended), result pages read as summaries; nothing installed or run
(D = documented, J = judgement). Question: is there a tool that fails the gate when a Nix module imports across a layer (host over `_shared/roles` over `_shared/modules`)?

| Candidate | Evidence (URL, read 2026-11-20) | Finding | Verdict |
|---|---|---|---|
| any import-graph linter for Nix | searches for "nix module layering lint", "nix forbidden imports", statix, deadnix, nix-tree, nix-diff, nixd returned nothing that enforces layers (D: absence of results, not proof) | statix and deadnix lint style and dead code; nix-tree and nix-diff inspect closures, not source imports | none exists, as far as found |
| written convention "import only downwards" | https://github.com/NotAShelf/nyx/blob/main/hosts/README.md (D: guideline, no linter) | layering by convention in a public config | not enforcement |
| one-way module imports (no `import` inside `imports`, reference paths so the module system tracks them) | https://fzakaria.com/2024/07/29/import-but-don-t-import-your-nixos-modules (D) | keeps the import graph visible to the module system, which is what a checker needs | a precondition, adopt it as a rule |
| module dependencies are not declared anywhere but `imports` | https://git.uninsane.org/colin/nixpkgs/src/commit/88d7aa56e14ea80d6005f3d1646bf6dad13f8673/nixos (D: nixpkgs commit removing needless imports) | the `imports` list is the only edge declaration | the checker reads it |
| the same idea in other ecosystems | https://nx.dev/docs/features/enforce-module-boundaries, https://vercel.com/docs/conformance/custom-rules/forbidden-imports (D) | tag layers, fail on a forbidden import: the pattern to copy | design reference |

## Verdict

No existing tool enforces layering for Nix. Two ways to get enforcement, neither adopted yet (J, untested):

1. **A shelf-owned recipe** (like `check_dockerfile_pins`): `nix-instantiate --parse` (or the `imports` lists read by a small parser) over each `.nix` file, a layer map in `docs/blueprint/blueprint.toml`
   (`[[layer]] name, paths, may_import`), a non-zero exit on a forbidden edge. Recommended: it is the import-linter shape, small, and one declaration. Needs the "no `import` inside `imports`" rule above.
2. **Evaluate each layer alone** (`lib.evalModules { modules = [ <layer> ]; }` for the lower layers in a flake check): a lower layer that reaches an upper one's option fails evaluation. Tool-free, but
   it only catches option references, not path imports, so it is a supplement.

Until one is built the nix profile's `architecture` role stays `na` with its reason (family `artifact`). Follow-up bead: build option 1 as a recipe with a red and a green fixture, then change the role to name it.
