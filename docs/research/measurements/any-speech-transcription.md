# Measurement: speech engines on Apple Silicon, 2026-11-19

Machine: Apple M3 Max, 36 GB, macOS 26 (Darwin 25.6). Nothing else heavy ran, except where noted. Every number below was
produced in this session by the scripts in [`packages/any-speech/bench/harness.md`](../../../packages/any-speech/bench/harness.md);
numbers I did not produce are marked **cited** or **untested**.

## Method

| item | value |
|---|---|
| Clips | Solek (channel `UCd190n-WQVHPC2l5gu0E2QQ`), Russian, one host. `xb3` 8.7 min (essay about a music genre, with music samples), `iS2` 15.4 min, `Th2O` 57.4 min. A 5 min cut of `Th2O` (600-900 s) for diarisation |
| Audio | decoded to 16 kHz mono wav with ffmpeg, once, for every engine |
| Reference text | **none**. "Agreement" is `difflib` word-sequence ratio against Parakeet-MLX, not accuracy. Nobody listened to the clips |
| Memory | `/usr/bin/time -l`: *maximum resident set size* (RSS) and *peak memory footprint* (includes GPU buffers MLX holds); for MLX also `mx.get_peak_memory()` with `mx.set_cache_limit(512 MB)` |
| Speed | wall seconds of the transcribe call (model already loaded unless marked first run) |
| Private audio | none used. No call recording was touched (no permission given) |
| Whisper baseline | the `transcript.local.json` channel-research already made beside each clip (turbo, forced `ru`, verbatim prompt, 512 MB cache cap); I re-ran Whisper myself only on `xb3` |

Versions: parakeet-mlx 0.7.0, mlx 0.32.4, mlx-whisper 0.4.3, sherpa-onnx 2.0.2, FluidAudio checkout `0b1f4628` (the one Reco builds).

## Speech to text

| engine | clip | speed | RSS | peak (MLX / footprint) | words | notes |
|---|---|---|---|---|---|---|
| FluidAudio CLI, Parakeet v3 | xb3 8.7 min | 6.4 s (81x) after a 20 s first-run CoreML compile | 0.53 GB | footprint 0.08 GB (Neural Engine memory is not counted in either figure) | 1098 | word times and confidence |
| FluidAudio CLI, Parakeet Ultra | xb3 | 5.1 s (101x) | 0.68 GB | n/a | 1117 | 3 `<unk>` |
| same | iS2 15.4 min | 3.6 s (261x) | 0.21 GB | n/a | | 2 `<unk>` |
| same | Th2O 57.4 min | 11.6 s (297x) | 0.37 GB | n/a | | **31 `<unk>`** |
| parakeet-mlx v3, unchunked | xb3 | 14.3 s | 2.0 GB | **MLX 14.5 GB** | 2891 tokens | a stray `<unk>` opens the text. This is lesson 1 again |
| parakeet-mlx v3, chunk 120 s, overlap 15 s | xb3 | 7.6 s (68x) | 0.79 GB | MLX 3.25 GB | 1091 | |
| same | iS2 | 15.9 s | 0.67 GB | MLX 3.28 GB / footprint 3.74 GB | 2427 | |
| same | Th2O 57.4 min | 56.6 s (61x) | 0.86 GB | MLX 3.44 GB / **footprint 4.09 GB** | 8412 | over 4 GB by footprint |
| same, chunk 30 s | iS2 | 25.8 s | n/a | MLX 2.76 GB / footprint 3.39 GB | 2424 | agrees 0.956 with chunk 120: boundaries move |
| sherpa-onnx, Parakeet v3 int8, CPU, 60 s windows | xb3 | 16.0 s | 2.6 GB | n/a | 1082 | text only; token timestamps not tried |
| same | iS2 / Th2O | 28 s / 106 s | 2.7 / 3.2 GB | n/a | 2408 / 8401 | |
| mlx-whisper large-v3-turbo, forced `ru`, verbatim prompt | xb3 (my run) | 26.7 s | 2.06 GB | MLX 2.49 GB | 1093 | |
| same, baseline | Th2O 57.4 min | 152 s (23x) | n/a | **MLX 4.16 GB**, cache capped | 8376 | over the 4 GB budget |
| same, baseline | iS2 | 46 s | n/a | not recorded | 2433 | |
| faster-whisper tiny, CPU int8 (personal-brand) | | | | | | **untested** here |

Whisper: with no prompt, same `xb3` run: 22.7 s, 2.71 GB. Letting Whisper auto-detect the language: it said `ru` on this clip (24 s), so the
latch was **not reproduced**; the K Research [181] failure was on mixed Russian/English call audio, which I did not use. **Untested.**

### Fillers kept (counts in the whole transcript)

| clip | engine | words | «ну» | «типа» | «как бы» | «вот» | «короче» |
|---|---|---|---|---|---|---|---|
| Th2O 57 min | Parakeet-MLX v3 | 8412 | **31** | 18 | 4 | 78 | 2 |
| | FluidAudio Ultra | 8447 | 27 | 18 | 5 | 79 | 2 |
| | sherpa Parakeet | 8401 | 25 | 17 | 5 | 76 | 2 |
| | Whisper + filler prompt | 8285 | **20** | 17 | 5 | 71 | 2 |
| iS2 15 min | Parakeet-MLX / Ultra / sherpa / Whisper | | 13 / 13 / 9 / 11 | 2 each | 3 each | 18 / 18 / 18 / 17 | 0 each |

- Parakeet keeps more «ну» than Whisper even with Whisper's filler prompt (31 vs 20 over 57 min). That is one clip and one speaker; it is the direction, not a rate.
- «э-э», «эм»: **0 in every engine on every clip**, because this host does not say them (checked in the Whisper output too). The lesson-5 claim that a
  model keeps «э-э» is therefore **untested**: it needs a clip with hesitations. The call recordings would have them; I did not use them.
- Whisper wrote a credit line, «Субтитры сделал DimaTorzok», twice on `xb3` (in the baseline). Parakeet wrote nothing of the kind on any clip.
- Punctuation: all three produce it.

### Agreement with Parakeet-MLX (word ratio, no reference)

| clip | FluidAudio Ultra | sherpa | Whisper |
|---|---|---|---|
| xb3 | 0.922 | 0.908 | 0.912 |
| iS2 | 0.960 | 0.934 | 0.918 |
| Th2O | 0.956 | 0.943 | 0.911 |

Whisper differs most from the three Parakeet runs, which agree with each other more. That says Whisper is the odd one out, not that it is worse. Which is right needs a reference text.

## Diarisation

| engine | clip | speed | RSS | result |
|---|---|---|---|---|
| Nemotron 3 via FluidAudio, `gpu` | Th2O 5 min | 10.8 s (28x) | 0.43 GB | 2 voices, 8 turns: voice B speaks 59.8-90.9 s and 154-158 s |
| same | xb3 8.7 min | 20.2 s (26x) | 0.52 GB | 6 voices, 85 turns, from an essay with music samples; **not checked by ear** |
| sherpa-onnx: pyannote segmentation 3.0 + 3D-Speaker embedding, fast clustering at threshold 0.5 | Th2O 5 min | 45.7 s | 0.46 GB | **8 voices**, 11 turns, against Nemotron's 2 on the same minutes; the threshold was not tuned |
| pyannote (torch, Hugging Face token) | | | | **untested**: needs a token and torch |

Nemotron's voice-B turns on `Th2O` (59.8-90.9 s) are the same stretch the embedding test below treats as the guest. Neither was verified against a listener.

## Voice embedding (host matching across videos)

Each cell is the cosine of two 30 s clips. `solek_*` come from two videos of the host (`xb3`, `iS2`); `th2o_spk0_*` and `th2o_spk1` are
Nemotron's two voices in `Th2O`. Whether `spk0` is the same person as the Solek host was not verified by ear; the scores suggest it.

| pair | 3D-Speaker ERes2Net (39 MB, trained mostly on Chinese) | WeSpeaker ResNet34 (26 MB, English VoxCeleb) |
|---|---|---|
| same video, same voice | 0.868 (xb3), 0.882 (Th2O spk0) | 0.938, 0.974 |
| other video, probably same host | 0.64-0.81 | 0.82-0.95 |
| host vs the other voice in Th2O | **0.09-0.19** | **0.60-0.66** |

3D-Speaker leaves the largest gap between "host" (>= 0.64) and "other voice" (<= 0.19) on these clips; WeSpeaker's gap is 0.6 vs 0.8. A threshold
is the consumer's: with these clips a cut near 0.4 would separate them, but five clips are not a calibration. FluidAudio's own `campplus-embed` command exists and was not tried.

## Install weight

| engine | weight |
|---|---|
| FluidAudio CLI | 22 MB binary; build 129 s from the checkout (needs Xcode's Swift); CoreML models fetched on first use: Parakeet v3 0.46 GB, Ultra 0.60 GB, Nemotron diarisation 0.38 GB |
| parakeet-mlx | venv 0.55 GB (mlx, numpy ...); model downloaded from Hugging Face on first use, size not measured |
| mlx-whisper | venv 1.1 GB; model size not measured |
| sherpa-onnx | venv 65 MB; Parakeet int8 model 0.64 GB; speaker models 26-39 MB; segmentation 7 MB |

Licences: **not read this session** for any model or package. Do not rely on this note for them.

## Verdicts

| engine / piece | verdict | reason |
|---|---|---|
| FluidAudio CLI, Parakeet **v3**, as the default ASR | ✅ do | 0.2-0.7 GB RSS, 81-297x real time, 57 min in 12 s, word times and confidence, fillers kept, no language flip seen. Cost: a Swift build, and the Neural Engine memory is outside the figure |
| FluidAudio **Ultra** | ⚠️ not the default | 31 `<unk>` in 57 min against 1 for v3; the adapter cuts `<unk>` out. The WER gain (14.81 to 11.67 %) is Reco's **cited** figure, not reproduced: no reference text |
| Nemotron 3 diarisation via FluidAudio | ✅ do | 26-28x, 0.4-0.5 GB, 2 voices on the 5 min clip. Accuracy not verified against ground truth here (Reco measured 4 voices in 17 min, **cited**) |
| parakeet-mlx, chunked | ✅ do, as the pure-Python fallback | 3.3-3.4 GB MLX peak, but 4.09 GB footprint at 57 min, which is over the 4 GB budget; the guard reads the MLX figure. Unchunked it needs 14.5 GB: never run it unchunked |
| mlx-whisper | ❌ refuse | 4.16 GB at 57 min (over budget), 13x slower than FluidAudio at 57 min, fewer fillers kept, a hallucinated credit line. Its latch is **cited**, not reproduced |
| sherpa-onnx Parakeet ASR | ❌ refuse for now | same model as FluidAudio, 9x slower, 3.2 GB; only useful off Apple Silicon (**untested** there) |
| sherpa-onnx diarisation | ❌ refuse | 8 voices where Nemotron found 2, 4x slower; the threshold is untuned, so it is not proven wrong |
| sherpa-onnx speaker embedding, 3D-Speaker ERes2Net | ✅ do | 39 MB, 4 s to load, the widest gap on these clips |
| pyannote | untested | needs a Hugging Face token and torch; not run |
| faster-whisper tiny | untested | personal-brand calls it "imperfect machine evidence" itself |
| captions as a source | untested | the format holds `source: "captions"`; no caption was parsed |
| Mixed Russian/English audio, language latch, «э-э» fillers, call recordings | untested | no permission to use calls; no hesitation-rich clip |

## What was not done

- No accuracy number: there is no reference text. Agreement ratios are only relative.
- No test on audio with two people talking over each other, or on mixed languages.
- Memory for the FluidAudio engines excludes what the Neural Engine uses; the system-wide effect was not measured.
- Peak memory was taken once per clip, not repeated.
