## Why

"Audio in, transcript with timestamps and speakers out" is written again in every project. Four consumers do it today, each with its own copy of the same lessons (or none of them):

| consumer | what it runs now | what it lacks |
|---|---|---|
| channel-research (iorlas-wip plugin) | `scripts/transcribe.py`: mlx-whisper large-v3-turbo, own flock, own failure file, own MLX cache cap | no diarisation; no host voice match across videos; lock and queue code is private to the script |
| Reco 2 (Swift app) | FluidAudio: Parakeet v3 → Ultra, Silero VAD, Nemotron 3 diarisation | not Python; stays Swift. It is a source of decisions and a possible reader of the format |
| iorlas-perform `heard.py` | mlx-whisper, `language="ru"`, text only | no lock, so it loads a second Whisper beside channel-research's |
| personal-brand wave3 `transcribe_missing.py` | faster-whisper `tiny`, CPU, int8 | marked "imperfect machine evidence"; no provenance contract |

Other searches under `~/Workspaces` (whisper, parakeet, pyannote, sherpa, FluidAudio) found no further live consumer; `call-transcripts-staging` holds Reco's older transcripts (readers of the format), not an engine.

## Evidence this change stands on

- Reco `embed-transcription` (K Research [181]): mlx-whisper large-v3 latched a misdetected language and destroyed whole tracks (11 of 549 transcripts held CJK text, 3 lost a track). Apple `SpeechTranscriber` has no Russian. Parakeet TDT 0.6b v3 never flipped language, lost nothing, ran 2-4x faster. Weights about 3.4 GB.
- Reco `diarize-speakers`: Nemotron 3 Diarization via FluidAudio; 17 min of system audio split into 4 voices in 44 s, two 0.2 s false blips in silence. Parakeet Ultra FLEURS mean WER 14.81 % → 11.67 %.
- channel-research 2026-11-19: uncapped MLX buffer cache passed 8 GB on an 18 min file and took a 36 GB Mac down on a 73 min file. Cap 512 MB held 3.1-3.5 GB, about 40 % slower.
- This change's own measurements: [measurement.md](measurement.md).

## What changes

New package `any-speech` (ADR 0015: the domain, not a backend):

- **Engine ports**: `Transcriber.transcribe(audio) -> Transcript`, `Diarizer.diarize(audio) -> Turns`, `Embedder.embed(audio) -> Voice`. Adapters are separate classes; a scripted fake lives in `any_speech.testing`.
- **Transcript format v1** (JSON, versioned): words, segments, speakers, provenance (engine, model, runtime, settings, audio hash, peak memory, duration, source kind `local` or `captions`), a `diarizer` outcome. Same fields in spirit as Reco's v3 (`speakers`, `diarizer`, `transcriber`, `transcriber_runtime`), so one reader can serve both.
- **Adapters, by measurement** (verdicts in the measurement note): FluidAudio CLI subprocess (ASR + Nemotron 3 diarisation), parakeet-mlx (pure-Python fallback), sherpa-onnx (voice embedding). mlx-whisper, sherpa-onnx ASR and diarisation, and pyannote are not built.
- **Parallel by slots**: `Speech(...).transcribe(path)` returns a Transcript; the owner sets how many transcriptions and diarisations run at once (`Slots`), machine-wide through `any-lease`. `Drain` runs a folder with N workers, claiming one file each.
- **A bad file never stalls the queue**: a failure record keyed to the file (size and mtime), skipped until the file changes.
- **Memory guard**: every engine reports a peak; a run over the budget (default 4 GB) is a failure, not a silent success.
- **CLI** `any-speech` on `verb-cli`: `transcribe`, `drain` (`--workers`, `--transcribe-slots`, `--diarize-slots`), `embed`, `match`.
- Catalog manifest, one use-case file per consumer, a ledger entry, a migration note for channel-research.

## Non-goals

- Swift stays in Reco. No code is taken from `~/Workspaces/reco`; its decisions and format are read.
- No streaming in v1.
- No speaker names. Diarisation separates voices; `S1` in one file is unrelated to `S1` in another. Matching across files is the embedder's job, with a threshold the consumer calibrates.
- No Reco-markdown reader or writer in v1; the JSON format maps to it field by field (design D3).
- No model download manager: each engine uses its own cache.
- pyannote is not built (needs a Hugging Face token and torch); see the measurement note.

## Impact

- New: `packages/any-speech/`, `catalog/any-speech.toml`, `use-cases/*--any-speech.toml`, `ledger/0037-*.toml`.
- Edited: root `pyproject.toml` (workspace source, testpaths, import-linter lists, marker `engines`), `uv.lock`.
- No tag, no release, no push. Consumers are not edited.
