# Changelog

## 0.6.0

- `# Any: <reason>` on the public signature that names `Any`; no behaviour or stored byte changes (shelf public-any rule, tests/test_arch_public_any.py)

## 0.5.0

- The stored `at` stamp (failure record, provenance) is written by any-clock `utc_stamp`; the bytes are unchanged (`2026-11-20T07:05:09Z`).
- **Breaking: renamed two Protocols that shared a name with another package's different contract** (`tests/test_arch_duplicate_names.py`): `Embedder` is `VoiceEmbedder` (anyembed's `Embedder` embeds text), and `setup.Run` is `StepRunner` (any-pipeline's `Run` is a stage's run). Nothing stored changes.
- **Breaking: the default file is `<stem>.speech.json`** (`talk.m4a` -> `talk.speech.json`, was `talk.m4a.speech.json`). Existing `<name>.speech.json` files are not found by the default name and are redone; pass `out` to keep one. `talk.m4a` and `talk.wav` now share a name.
- **Breaking: stored JSON is compact** (one line, no indent) with word and segment times rounded to milliseconds. Old files (full precision, indented) still load; `provenance.key` is unchanged, so they stay current. Segment text is kept in the file (see the README).
- `Transcript.to_markdown()`: the default view, a Reco transcript-v3 style YAML header plus `[MM:SS] S1: text` paragraphs. `any-speech text <file>` prints it.
- **Breaking: `env` and `home` are required** on `default_transcriber`, `default_diarizer`, `default_speech`, `transcribe` and `transcribe_with_speakers`; the library no longer falls back to `os.environ` or `Path.home()` (the CLI passes them). `install_fluidaudio` lost its `which=` argument: `swift` and `git` are found with `child_env.find` over `env`.
- Built on the owners: the child runner reads group memory with stream-proc's process table (`group_rss`, was a `ps` parse) and stops the tree with `stop_tree` (was `os.killpg`), also on Ctrl-C; ffprobe, ffmpeg and the setup build steps run through `capture` / `capture_bytes` with a timeout; hashes use content-digest `digest_file`. Stored `audio_sha256` and `runtime` are byte-identical (golden tests). Still local to `adapters/_child.py`: the spawn with `start_new_session=True` and `os.wait4`, because only wait4 returns the child's own `ru_maxrss` and stream-proc's `run`/`capture` reap the child and discard it; with it the one platform read (`ru_maxrss` is bytes on macOS, kilobytes on Linux). The 20 ms poll `time.sleep` runs on a worker thread (`blocking`), never on the event loop.

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
