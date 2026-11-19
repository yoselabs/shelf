# any-speech

**Stop caring which engine turns speech into words, turns and voices.** One versioned `Transcript` (words with times, speakers,
provenance) from engines behind small ports, one model per machine, and a voice embedding to recognise a host across files.
Composes [any-lease](../any-lease/README.md), [process-lock](../process-lock/README.md), [atomic-io](../atomic-io/README.md), [content-digest](../content-digest/README.md),
[app-dirs](../app-dirs/README.md) and [verb-cli](../verb-cli/README.md).

```python
from pathlib import Path
from any_speech import Drain, Job, Pipeline, Slots, Speech
from any_speech.adapters import FluidAudioCli, FluidAudioDiarizer

fa = Path("~/bin/fluidaudiocli").expanduser()          # built from FluidAudio: swift build -c release --product fluidaudiocli
pipeline = Pipeline(FluidAudioCli(fa, runtime="fluidaudio-0.17.5"), FluidAudioDiarizer(fa, runtime="fluidaudio-0.17.5"))

speech = Speech(pipeline, Path("~/.local/state/any-speech/leases").expanduser(), Slots(transcribe=2, diarize=1))

transcript = speech.transcribe(Path("talk.m4a"))                    # a path in, a Transcript out; waits if both slots are busy
transcript = speech.transcribe(Path("talk.m4a"), Path("talk.json"))  # the same, stored; a current file is reused, not redone

Drain(scan=lambda: jobs, speech=speech, workers=4).run()             # a folder: 4 workers, at most 2 transcribing at once
```

```bash
any-speech transcribe talk.m4a --engine fluidaudio --fluidaudio-bin ~/bin/fluidaudiocli --diarize
any-speech drain --engine fluidaudio ~/.local/share/channel-research --pattern 'youtube/*/videos/*/audio.m4a' --fluidaudio-bin ~/bin/fluidaudiocli --workers 4 --transcribe-slots 2 --diarize-slots 1
any-speech embed host.wav --out host.voice.json --voice-model 3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx
any-speech match clip.wav --voice host.voice.json --voice-model 3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx
```

## Contract

- **Format v1** (`Transcript.to_json`): `version`, `words[]` (`text`, `start`, `end`, `probability`, `speaker`), `segments[]`, `speakers`, `provenance`
  (`engine`, `model`, `runtime`, `settings`, `audio_sha256`, `audio_seconds`, `seconds`, `peak_memory_gb`, `diarizer`, `made_at`, `source` = `local` or `captions`, derived `key`).
  A reader refuses an unknown `version` (`UnknownVersionError`). Text is verbatim: nothing cleans fillers.
- **`Pipeline.run(audio)`** transcribes, labels each word with the diarizer turn it overlaps most, cuts segments at a speaker change, a pause of 0.5 s or 15 s, and records provenance.
  A diarizer failure never fails the transcript (words keep `speaker = None`, `provenance.diarizer` says why). A peak over `budget_gb` (4) raises `MemoryBudgetError`.
- **`Speech`** runs each model call in a slot: `Slots(transcribe, diarize)` units of an `any-lease` resource, shared by every process on the machine, freed by the kernel if the holder dies. A caller waits for a free unit. `transcribe(path, out)` reuses a current `out` and runs one job once however many callers ask.
- **`Drain`** takes `workers` threads; each claims one pending job (a lock beside its output) and rescans until none is left. A job is pending when its output is missing or its `provenance.key` (audio hash, engine, model, settings) differs. A failed file gets `<out>.failed.json` keyed to its size and mtime and is skipped until it changes.
- **Engines are optional.** `pip install any-speech[parakeet]` or `[embed]`; the FluidAudio adapter needs a built binary. Nothing is imported until its adapter runs.
- Measured numbers, the verdict per engine, and what is untested: [measurement note](../../openspec/changes/any-speech/measurement.md).

## Refused or untested

mlx-whisper (over the memory budget at 57 min), sherpa-onnx ASR and diarisation, and pyannote are not built. No streaming; no speaker names; no Reco markdown reader.
