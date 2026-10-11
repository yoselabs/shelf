# Nix conventions

Stack: nix (flakes; NixOS hosts or dev shells). The gate is `just check`; this file is what to know before changing a `.nix` file.

## Tools per role

| role | tool | configured in |
|---|---|---|
| toolchain | `flake.lock` beside every `flake.nix`; the Nix that runs the gate is pinned (never `nixos/nix:latest`) | `flake.lock`, the gate recipe |
| formatter | nixfmt (the official RFC 166 style), `nixfmt --check` | the gate recipe, hooks |
| linter | `statix check` and `deadnix --fail` (without `--fail` deadnix always exits 0) | `statix.toml` |
| types | evaluating every deployed output: `nix eval "path:<repo>?dir=hosts/<h>#nixosConfigurations.<h>.config.system.build.toplevel.drvPath" --raw` | the gate recipe |
| dependencies | every non-nixpkgs input follows the one nixpkgs (`inputs.<x>.inputs.nixpkgs.follows`) | `flake.nix` |
| tests | none yet: NixOS VM tests need a KVM builder; the evaluation is the gate | - |
| spelling | typos with a committed config | `typos.toml` |
| hooks | prek: nixfmt, statix, deadnix on staged files; the evaluation stays in pre-push `just check` | [gate.md](gate.md) |

## Rules

| rule | why |
|---|---|
| Never hand-edit `flake.lock`: `nix flake update <input>`, in its own commit, then re-run the evaluation | The lock is the pin; a bump is a reviewed change |
| Evaluate with a `path:` flake ref, not `git+file:` | `git+file:` skips uncommitted files, so the check passes on what you did not write |
| A new module is imported from the module set's `default.nix`, never only from one host | Otherwise a second host silently lacks it |
| A statix finding is fixed, or disabled in `statix.toml` with a reason; never a blanket disable | The disable list is the record of what was judged |
| Unused module arguments (`{ config, lib, pkgs, ... }:` with `config` unused) are trimmed | deadnix fails on them; trimming keeps the signature honest |
| Secrets are sealed (sops or agenix) and never enter the Nix store as plaintext | The store is world-readable |
| Evaluate before deploy; a host that does not evaluate is never switched to | Evaluation catches unknown options and failed assertions without touching the host |

## Run

```bash
just check          # the gate: format, lint, evaluate every host
nixfmt $(git ls-files '*.nix')   # format in place
```
