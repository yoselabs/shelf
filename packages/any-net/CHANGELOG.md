# any-net — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.3.0: runtime dependency on any-versioned; `last()` reads the `v` key through it, so a file with a missing or unknown `v` now reads as None (was read as today's format); `record` bytes unchanged
- 0.2.0: runtime dependency on atomic-io; `record(path, probe)` bytes unchanged (compact ASCII JSON, no trailing newline, no fsync), still never raises
