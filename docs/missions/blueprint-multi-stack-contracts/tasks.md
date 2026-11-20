# Tasks: blueprint outcome contracts across several stacks

Beads with acceptance criteria; tests first; Done = `just check` green over the whole repo. New checkpoints warn until the next audit (ADR 0018).

- [x] 1. List every checkpoint with: cost per run, which consumer overrides or ignores it, per-commit or audit-only. Cut or justify each (owner reviews the list).
- [x] 2. Write the adapter interface on paper against `dotnet.toml` and `python-uv.toml`; prove no Python assumption sits in the core. Output: `design` addendum. Done 2026-11-20: the proof failed, three real Python assumptions found (addendum items 1 to 3), owned by tasks 4 and 5 (not re-verified after they landed).
- [x] 3. Outcome contracts for `tests` and `coverage` roles; tool-agnostic coverage (closes shelf-2hl); regex `gate` kept only for command-shape roles.
- [x] 4. Profiles for `node`, `go`, `rust` including the `architecture` role (research the layering tool for each first, in `research/`); fitness test that every profile has one.
- [x] 5. Mixed-stack: per-stack steps in one gate, declared `[[edge]]` across stacks; fixture repo with Python plus Node.
- [x] 6. Secret scanning: read task-loop d6e223b71 and 739474b82; pin the scanner in `mise.toml`; staged, range and full modes; checkpoint.
- [x] 7. Hook anti-pattern checkpoints (design D6), each with a failing fixture and a passing fixture.
- [ ] 8. Rendered justfile: choose `import` versus `mod` with a throwaway fixture of two stacks; `blueprint render` and drift check; retire the justfile part of `tools/preset_drift.py`.
- [x] 9. Churn: verdict-change-only reports, per-checkpoint fingerprints, expiry notice, converge batching.
- [x] 10. Check a2kay's current gate result against the expired coverage override (read-only), and record.
- [ ] 11. Update `skills/blueprint/SKILL.md` and `agentic-delivery.md`; keep them as short as the contracts allow.
- [ ] 12. `just check` green; `just check-all` once; archive.
