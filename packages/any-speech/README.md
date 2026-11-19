# any-speech

```python
from any_speech import transcribe, transcribe_with_speakers

transcript = transcribe(Path("talk.m4a"))              # words with times; stored in talk.m4a.speech.json; returned too
transcript = transcribe_with_speakers(Path("talk.m4a"))  # the same, each word labelled S1, S2, ... by voice
print(transcript.to_text())                            # [00:00] S1: ну да ...   (a readable view of the same data)
```

That is the whole simple path: one file stored beside the audio, the same data returned as a `Transcript` (words, segments, provenance) for code
that wants a structure. A current file is reused, not redone. **Speakers are opt-in**: most uses do not need them and they cost a second model, so
`transcribe` is words only and `transcribe_with_speakers` is the second name for when you want them.
The default model is FluidAudio's Parakeet v3 (+ Nemotron 3 for speakers); slot counts are sized from the machine's memory. Replace any part by
name: `transcribe(path, out, transcriber=..., slots=Slots(...))`. A missing default engine raises `EngineMissingError` with the build command, and
**nothing falls back to another engine**: a script that wants another engine names it. `any_speech.CARDS` records why each model is or is not the choice,
with the evidence (Reco 2's decisions and our measurements) and what would reopen it; change a card in the same commit as the model.

**Stop caring which engine turns speech into words, turns and voices.** One versioned `Transcript` (words with times, speakers,
provenance) from engines behind small ports, one model per machine, and a voice embedding to recognise a host across files.
Composes [any-lease](../any-lease/README.md), [process-lock](../process-lock/README.md), [atomic-io](../atomic-io/README.md), [content-digest](../content-digest/README.md),
[app-dirs](../app-dirs/README.md) and [verb-cli](../verb-cli/README.md).

Advanced: name the parts yourself.

```python
from pathlib import Path
from any_speech import Drain, Job, Pipeline, Slots, Speech
from any_speech.adapters import FluidAudioCli, FluidAudioDiarizer

fa = Path("~/bin/fluidaudiocli").expanduser()
pipeline = Pipeline(FluidAudioCli(fa, runtime="my-build"), FluidAudioDiarizer(fa, runtime="my-build"), budget_gb=4)
speech = Speech(pipeline, Path("~/.local/state/any-speech/leases").expanduser(), Slots(transcribe=2, diarize=1, total=3))
transcript = speech.transcribe(Path("talk.m4a"))                     # waits for a free slot; stored beside the audio
Drain(scan=lambda: jobs, speech=speech, workers=4).run()             # a folder: 4 workers, at most 2 transcribing at once
```

```bash
any-speech setup fluidaudio                    # once: builds FluidAudio at the pinned commit (needs Xcode's Swift, about 3 min) and installs it
any-speech transcribe talk.m4a                 # words only, stored in talk.m4a.speech.json; add --diarize for speakers
any-speech drain ~/.local/share/channel-research --pattern 'youtube/*/videos/*/audio.m4a' --out-name transcript.speech.json
any-speech embed host.wav --out host.voice.json --voice-model 3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx
any-speech match clip.wav --voice host.voice.json --voice-model 3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx
```

## Speed (Apple M3 Max, 36 GB, FluidAudio Parakeet v3, 2026-11-19)

| run | files | audio | wall | note |
|---|---|---|---|---|
| `any-speech drain`, words only, no path flags, 2 workers | 9 | 297 min (Solek) | **64 s** | peak resident of the drain process 0.4 GB; the 73 min file took 34 s, the 57 min file 18.5 s |
| same, nothing left to do | 9 | | 5 s | in-process hash cache; most of it is Python and `uv` start |
| with Nemotron diarisation (consumer's measurement, 0.1.0) | 9 | 297 min | 753 s | diarisation is about 87% of it |

The binary is found, in order, from `ANY_SPEECH_FLUIDAUDIO_BIN`, the folder `any-speech setup fluidaudio` installs into, PATH, then `~/.local/bin`.
`provenance.runtime` is derived: `fluidaudio-<commit>+<sha256 of the binary, 12 hex>`, with `unknown` for the commit when the binary was not built by `setup`.

## Contract

- **Format v2** (`Transcript.to_json`): `version`, `words[]` (`text`, `start`, `end`, `probability`, `speaker`), `segments[]`, `speakers` (`{"S1": {"name": "voice 1", "seconds": 912.4, "words": 2310}}`: seconds are the sum of the voice's word durations, so a 3 s music sample is told from the host at a glance), `provenance`
  (`engine`, `model`, `runtime`, `settings`, `audio_sha256`, `audio_seconds`, `seconds`, `peak_memory_gb`, `diarizer`, `made_at`, `source` = `local` or `captions`, derived `key`).
  A reader loads v1 (its `speakers` was label to name only; the amounts are worked out from the words) and v2, and refuses any other `version` (`UnknownVersionError`). Text is verbatim: nothing cleans fillers.
- **`Pipeline.run(audio)`** transcribes, labels each word with the diarizer turn it overlaps most, cuts segments at a speaker change, a pause of 0.5 s or 15 s, and records provenance.
  A diarizer failure never fails the transcript (words keep `speaker = None`, `provenance.diarizer` says why). A peak over `budget_gb` (4) raises `MemoryBudgetError`.
  **The FluidAudio engines are guarded live**: each runs in its own process group whose resident memory is read every 0.5 s, and a group over the budget is killed (`MemoryBudgetError`; the drain records the failure and moves on). `ParakeetMlx` runs in-process, so its guard is after the fact and reads MLX's own figure (3.44 GB at 57 min while the process footprint was 4.09 GB); it also serialises its calls with a lock, because one MLX model is not known to be thread-safe.
- **`Speech`** runs each model call in a slot: `Slots(transcribe, diarize)` units of an `any-lease` resource, shared by every process on the machine, freed by the kernel if the holder dies. A caller waits for a free unit. `transcribe(path, out)` reuses a current `out` and runs one job once however many callers ask.
- **`Drain`** takes `workers` threads; each claims one pending job (a lock beside its output) and rescans until none is left. A job is pending when its output is missing or its `provenance.key` (audio hash, engine, model, settings) differs. A failed file gets `<out>.failed.json` keyed to its size and mtime and is skipped until it changes. A transcript whose **diarizer** failed (words kept, `diarizer.status = failed`) is not current: the next drain redoes it, up to 3 tries (`diarizer.tries`), then keeps `speaker = None`. A job runs once per drain. Each audio file is hashed once per process (path, size, mtime).
- **Engines are optional.** `pip install any-speech[parakeet]` or `[embed]`; the FluidAudio adapter needs a built binary. Nothing is imported until its adapter runs.
- Measured numbers, the verdict per engine, and what is untested: [measurement note](../../openspec/changes/any-speech/measurement.md).

## Refused or untested

mlx-whisper (over the memory budget at 57 min), sherpa-onnx ASR and diarisation, and pyannote are not built. No streaming; no speaker names; no Reco markdown reader.
