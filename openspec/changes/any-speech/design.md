## Decisions

### D1 — Name and shape
`any-speech`: the consumer stops caring which engine turns speech into words, turns and voices. The thing the domain has is a **Transcript** (words with times, speakers and provenance), so that is the type consumers hold; engines are adapters behind three small ports. (`any-transcript` was rejected: it names the output only, and diarisation and embedding are not transcripts.)

### D2 — Ports
```
Transcriber.transcribe(audio: Path, *, language: str | None) -> Transcript
Diarizer.diarize(audio: Path)                                -> Turns          # (start, end, label) by first appearance S1..Sn
Embedder.embed(audio: Path, *, start=None, end=None)         -> Voice          # unit vector + model id
```
Each adapter exposes `identity` (engine, model, runtime). Arguments are paths; an adapter that needs 16 kHz mono converts through `ffmpeg` itself. A consumer injects instances; nothing is global (constitution II).

`transcribe_with_speakers(audio, transcriber, diarizer | None)` runs both and assigns each word the label whose turn overlaps it most. A diarizer failure never fails the transcript (Reco D6): words keep `speaker = None`, and `provenance.diarizer` records `{"status": "failed", "detail": ...}`.

### D3 — Transcript format v1
JSON, one file per audio. `version: 1` is bumped only on an incompatible shape change; a reader refuses a version it does not know.

| key | meaning | Reco v3 counterpart |
|---|---|---|
| `version` | format version | `transcript_version` |
| `source` | `local` or `captions` | (none; Reco is always local) |
| `words[]` | `text`, `start`, `end` (seconds), `probability` (0-1 or null), `speaker` (label or null) | body turns, finer |
| `segments[]` | `start`, `end`, `text`, `speaker` | a body turn |
| `speakers` | label → free text (`"S1"`: `"voice 1"`) | `speakers` |
| `provenance.engine`, `.model`, `.runtime` | what ran | `transcriber`, `transcriber_runtime` |
| `provenance.settings` | the exact options | (none) |
| `provenance.audio_sha256`, `.audio_seconds` | the input | `audio.session_duration_sec` |
| `provenance.seconds`, `.peak_memory_gb` | cost | (none) |
| `provenance.diarizer` | `{"model": ..., "status": "ok" or "failed" or "not_run"}` | `diarizer` |
| `provenance.made_at`, `.key` | when; `digest(audio_sha256, engine, model, settings)` | `transcribed_at` |

Verbatim rule: the format keeps what the engine heard. It never cleans fillers; cleaning is a consumer's choice. Captions are `source: "captions"` with `probability = null` and the engine fields naming the provider (for example `youtube-auto`).

Reco keeps its markdown; a reader maps `[MM:SS] speaker: text` turns to `segments` and `transcriber` to `provenance.model`. No markdown code in v1 (non-goal).

### D4 — Adapters (verdicts in measurement.md)
| adapter | does | runs as |
|---|---|---|
| `FluidAudioCli` | ASR (v3 or ultra) with word times and confidence, Nemotron 3 diarisation | subprocess of a prebuilt `fluidaudiocli`; path injected |
| `ParakeetMlx` | ASR, chunked 120 s with 15 s overlap | in process, MLX, cache capped |
| `SherpaEmbedder` | voice embedding (wespeaker ONNX) | in process, CPU |

Engines are imported lazily, inside the adapter, behind extras (`any-speech[parakeet]`, `[embed]`); the core imports none. `language` is not a port argument: Parakeet v3 auto-detects across its 25 languages and never latched on the clips measured.

**Refused: mlx-whisper.** The measurement note shows it over the 4 GB budget at 57 minutes (4.16 GB MLX peak with the cache capped), 13x slower than FluidAudio, with fewer fillers kept and a hallucinated credit line. No adapter is built; the settings that worked are recorded in measurement.md so a consumer that needs a language outside Parakeet's 25 can add one (one file, `any_speech/adapters/`).

### D5 — Slots, not one lock (changed after the owner's brief: parallel, not sequential)
The front door is `Speech(pipeline, leases_root, Slots(transcribe=2, diarize=1)).transcribe(path, out=None) -> Transcript`.
- Each model call (`Transcriber.transcribe`, `Diarizer.diarize`) runs inside a **slot**: an `any-lease` unit of the named resource `any-speech-transcribe` or `any-speech-diarize`, `limit` units each. Machine-wide (the leases folder is shared), kernel-released on death, a caller waits when all units are taken. Transcription and diarisation have separate pools, so they overlap.
- `transcribe(path, out)`: a current file at `out` (same audio hash, engine, model, settings: `provenance.key`) is returned as is; else the result is saved there. Two callers for one `out` run it once: a claim lock (`process-lock`, `<out>.claim`) makes the second wait and then find it done.
- `Drain(scan, speech, workers=N)`: N threads, each claims a pending job (non-blocking claim lock, so no two workers or processes take one file), runs it, rescans until nothing is claimable. Total parallelism is min(workers, slots) per machine, whatever the number of processes.
- No separate queue package (`AnyQ`): the queue is "wait for a unit" (any-lease) plus "scan for pending work" (Drain); a third piece would be a second copy of either.
- The model loads per call in the FluidAudio adapter (a subprocess per file, CoreML compile cached by the OS); in-process MLX adapters load once per adapter instance.

### D10 — The simple path and the model cards (added after the owner's brief)
`any_speech.transcribe(path, out=None)` is the whole simple API: the default model (FluidAudio Parakeet v3, found via `ANY_SPEECH_FLUIDAUDIO_BIN`, PATH or `~/.local/bin`), slots sized from memory (`Slots.auto`: one call per 12 GB, at most 4, half as many diarizations), leases under the state dir. The result is stored in one file beside the audio (`<name>.speech.json`, or `out`) and returned as a `Transcript`; `to_text()` renders `[MM:SS] S1: text`. **Diarisation is opt-in and in the same package**: most uses need no speakers and pay a second model for them, so `transcribe` is words only and `transcribe_with_speakers` adds the default diarizer (two names, not a flag; a separate package would only add glue for merging speakers onto words). A words-only file is not reused for a speakers request, because the diarizer is part of the key. Each part is replaced by naming it: `transcriber=`, `diarizer=`, `slots=`, `leases_root=`. A missing default engine raises `EngineMissingError` with the build command; it never falls back, because a fallback that quietly changes the model changes the transcripts. `any_speech.models.CARDS` is the selection trace: one `ModelCard` per model with status (default, available, refused, untested), the reason, the evidence (Reco's OpenSpec changes and `measurement.md`) and `revisit`, what would reopen the verdict. Tests tie each adapter identity to a card, so a model cannot change without its card.

### D6 — Failure ledger
`<output>.failed.json` beside the output: `{error, audio_size, audio_mtime_ns, at, engine, model}`. A job whose audio still has that size and mtime is skipped; a changed file retries; deleting the record retries. Written with `atomic-io`.

### D7 — Memory budget
Default 4 GB per model process. Adapters report `peak_memory_gb` (MLX `get_peak_memory`; subprocess `ru_maxrss` of the child). `guard.check(peak, budget)` raises `MemoryBudgetExceeded`; the drain records that as a failure for the file. MLX adapters set `mx.set_cache_limit(512 MB)` before the first run and `mx.clear_cache()` after each file. A long-audio test in the `engines` lane proves the figure for each in-process adapter; the catalog manifest carries the measured peak.

### D8 — Reuse (DEEP · STABLE · WINS)
| piece | verdict |
|---|---|
| `process-lock` (flock) | adopt: the per-output claim; any-lease itself rests on it |
| `atomic-io` (crash-safe JSON) | adopt |
| `content-digest` (canonical hash) | adopt for `key` |
| `app-dirs` (state dir) | adopt |
| `verb-cli` | adopt for the CLI |
| `any-lease` | adopt: N units of a named resource across processes is exactly the slot pool |
| `jsonl-log` | refuse: failure records are per file, not a log |
| `stream-proc`, `any-proc` | refuse for v1: one blocking `subprocess.run` with a timeout is enough; revisit if a hung engine needs tree-kill |

The drain and failure ledger are generic (any batch job behind one machine-wide model). They start inside `any-speech`; reconcile when a second batch consumer appears.

### D9 — Speaker embedding for host matching
`Voice` is a unit vector plus its model id; `similarity(a, b)` is the dot product and refuses vectors of different models. `any-speech match` embeds a clip and compares it to a stored host voice. The threshold is the consumer's: measurement.md gives the same-voice and different-voice scores observed, not a universal number.
