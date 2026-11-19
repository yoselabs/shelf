# Changelog

## 0.2.0

- `transcribe(path, out=None, **overrides)`: the default models and slots, each part replaceable by name; `EngineMissingError` instead of any fallback.
- `CARDS`: why each model is or is not the choice, with evidence and what would reopen it; tests tie adapter identities to cards.
- Slots (`any-lease`): separate transcribe and diarize pools plus a shared total; `Speech`, `Drain(workers)`; transcription and diarisation overlap on one file.
- CLI: `--engine` defaults to the default model; the binary is found without a flag.

## 0.1.0

- Transcript format v1, ports, Pipeline, Drain, failure records, memory guard, adapters, CLI.
