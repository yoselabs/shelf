# Migration note: channel-research `scripts/transcribe.py` on any-speech

For the session that owns `iorlas-wip`; this change edits nothing there. Read `extraction.md`, `scripts/transcribe.py`, `scripts/cr_common.py` first.

## What the script owns today, and where it goes

| in `transcribe.py` / `cr_common.py` | becomes |
|---|---|
| `machine_lock("transcribe")` flock, wait, drain-and-rescan | `Speech` slots (`any-lease`, kernel-released like the flock, but N at a time: set `Slots(transcribe=2)`) and `Drain(workers=N)`; the leases folder is shared by every consumer on the machine |
| `pending()`: audio without a transcript from this model | `Drain(scan=...)` returns `Job(audio, out)`; "current" is `provenance.key` (audio hash, engine, model, settings), not the model name alone |
| `transcript.error.json` keyed to `audio_size` | `<out>.failed.json` keyed to size and mtime, written by the drain |
| `mx.set_cache_limit(512 MB)`, `mx.clear_cache()` | inside `ParakeetMlx`; the FluidAudio engine needs no cap |
| `PROMPT`, `SETTINGS` (Whisper) | gone with Whisper (refused: 4.16 GB at 57 min, fewer fillers, hallucinated credit line); engine settings sit in `provenance.settings` |
| `write_json(transcript.local.json, {...})` | `Transcript.save(videos/<id>/transcript.local.json)` |

## The script after the move (about 25 lines)

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["any-speech @ git+https://github.com/yoselabs/shelf@any-speech-v0.1.0#subdirectory=packages/any-speech"]
# ///
fa = Path(os.environ["FLUIDAUDIO_BIN"])
pipeline = lambda: Pipeline(FluidAudioCli(fa, runtime=RUNTIME), FluidAudioDiarizer(fa, runtime=RUNTIME))
scan = lambda: [Job(a, a.with_name("transcript.local.json")) for a in sorted(ROOT.glob("youtube/*/videos/*/audio.*"))]
speech = Speech(pipeline(), LEASES, Slots(transcribe=2, diarize=1))
Drain(scan=scan, speech=speech, workers=2).run()
```

(Or `any-speech drain ROOT --pattern 'youtube/*/videos/*/audio.*' --out-name transcript.local.json --diarize --fluidaudio-bin ...`; the first channel goes first by passing its glob first.)

## Changes the readers must absorb

| reader | before | after |
|---|---|---|
| word list | `words[].w`, `.p` | `words[].text`, `.probability`; times are seconds, unrounded |
| speaker | `speaker: null` at file level | `words[].speaker` is `S1`..`Sn` or null; `speakers` lists them; `provenance.diarizer.status` says ok, failed or not_run |
| `model`, `settings`, `made_at`, `secs`, `mlx_peak_gb` | top level | `provenance.model`, `.settings`, `.made_at`, `.seconds`, `.peak_memory_gb` |
| `source: "local"` | top level | `provenance.source`; captions become `"captions"` with `probability = null` |

Existing `transcript.local.json` files (Whisper, old shape) are not rewritten: a reader that sees no `version` key treats the file as the old shape. They are not "current" for the drain because their `provenance.key` is absent, so the drain would redo all 89 videos on first run (about 12 s per hour of audio on FluidAudio). Decide whether to keep both files side by side (use `--out-name transcript.speech.json`) or replace.

## Host identification (new)

1. Pick 30-60 s of the host from one video where the diarizer found one voice. `any-speech embed clip.wav --start 20 --end 50 --out host.voice.json ...`.
2. For each other video and each diarised voice, embed its longest turn and `match`. Measured on the Solek clips with 3D-Speaker ERes2Net: same host 0.64-0.88, a guest 0.09-0.19. Calibrate the cut on your own channel before trusting it.
3. Store the host's voice file under the channel's data root; it is one model's vector, so a model change means re-embedding.

## Not done in this change

Nothing in `iorlas-wip` was touched. The verbatim claim for «э-э» is untested (the Solek host says none), so the first run on a hesitation-heavy channel should be spot-checked before `extraction.md` relies on it.
