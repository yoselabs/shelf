# Changelog

## 0.5.0

- **Breaking: the default file is `<stem>.speech.json`** (`talk.m4a` -> `talk.speech.json`, was `talk.m4a.speech.json`). Existing `<name>.speech.json` files are not found by the default name and are redone; pass `out` to keep one. `talk.m4a` and `talk.wav` now share a name.
- **Breaking: stored JSON is compact** (one line, no indent) with word and segment times rounded to milliseconds. Old files (full precision, indented) still load; `provenance.key` is unchanged, so they stay current. Segment text is kept in the file (see the README).
- `Transcript.to_markdown()`: the default view, a Reco transcript-v3 style YAML header plus `[MM:SS] S1: text` paragraphs. `any-speech text <file>` prints it.

## 0.4.0

- **Breaking: asyncio-native.** `transcribe`, `transcribe_with_speakers`, `Speech.run/transcribe/fulfil`, `Pipeline.run`, `Drain.run` and `is_current` are `async def`; the CLI is unchanged. Sync scripts: `asyncio.run(...)`.
- `Pipeline` is built on any-pipeline: `gather(hear, diarize) >> assemble`, a diarizer failure is a value (`Voices` with the reason), a memory-budget failure keeps its `MemoryBudgetError` type.
- A stored diarizer failure's `detail` now starts with the exception type (`RuntimeError: model missing`).

## 0.3.0

- `transcribe(path)` stores one file beside the audio (`<name>.speech.json`) and returns the `Transcript`; words only. `transcribe_with_speakers(path)` is the opt-in speaker version. `NO_DIARIZER` is gone (breaking).
- `Transcript.to_text()`: `[MM:SS] S1: text`.
- `Slots.auto()`: slot counts from the machine's memory; `Slots` has no defaults and the CLI slot flags are optional (breaking for `Slots()`).
- `Speech.run(audio)` returns a transcript without storing; `Speech.transcribe(audio)` stores by default (breaking: it stored nothing without `out`).

- Live memory guard: FluidAudio runs in its own process group, read every 0.5 s, killed over `budget_gb` with `MemoryBudgetError`; `ParakeetMlx` documents its after-the-fact guard and serialises calls with a lock.
- `any-speech setup fluidaudio` builds the pinned commit (0b1f4628) and installs it; `find_fluidaudio` order: env, installed copy, PATH, `~/.local/bin`; `provenance.runtime` is `fluidaudio-<commit>+<sha256[:12]>`; `--fluidaudio-bin` optional.
- `AudioHasher`: one hash per file per process; `Pipeline(hasher=...)`.
- A failed diarizer is retried by the next drain, at most 3 times; a job runs once per drain.
- Format v2: `speakers` maps a label to `{name, seconds, words}` (`Speaker`); v1 files still load (breaking for code that read `speakers` values as strings).

## 0.2.0

- `transcribe(path, out=None, **overrides)`: the default models and slots, each part replaceable by name; `EngineMissingError` instead of any fallback.
- `CARDS`: why each model is or is not the choice, with evidence and what would reopen it; tests tie adapter identities to cards.
- Slots (`any-lease`): separate transcribe and diarize pools plus a shared total; `Speech`, `Drain(workers)`; transcription and diarisation overlap on one file.
- CLI: `--engine` defaults to the default model; the binary is found without a flag.

## 0.1.0

- Transcript format v1, ports, Pipeline, Drain, failure records, memory guard, adapters, CLI.
