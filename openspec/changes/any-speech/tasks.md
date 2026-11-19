1. Tests first (red): format round trip and version refusal; speaker assignment; fake engines; slots (peak concurrency equals the slot count, a busy pool makes a caller wait), drain (claims, rescan, failure skip, key change re-run); memory guard; word merge for Parakeet tokens; adapter parsers against recorded engine output.
2. Implement `format`, `ports`, `testing`, `assign`, `speech` (slots), `drain` (claims, workers), `failures`, `guard`.
3. Adapters: `fluidaudio`, `parakeet_mlx`, `sherpa_embed`; lazy imports so the core needs none of them.
4. CLI on verb-cli.
5. Engine lane (`-m engines`, off by default): real-model contract tests and the long-audio memory guard.
6. Measurement note with numbers; bench scripts under `packages/any-speech/bench/`.
7. Catalog manifest, use-cases, ledger, README, CHANGELOG; `just catalog`.
8. Migration note for channel-research.
9. `just check` green; beads closed.
