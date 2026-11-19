# Measurement harness (2026-11-19)

Throwaway scripts that produced `openspec/changes/any-speech/measurement.md`. Kept as text, not code: they are
not part of the gate. Each ran in its own venv (`uv venv; uv pip install parakeet-mlx | mlx-whisper | sherpa-onnx`) from the
clips in a scratch folder; peak memory is `/usr/bin/time -l` (`maximum resident set size`, `peak memory footprint`) plus MLX's own `get_peak_memory`.
FluidAudio: `swift build -c release --product fluidaudiocli` on the checkout Reco pins (0b1f4628), then `fluidaudiocli transcribe|nemotron3-diarize`.

## run_parakeet.py

```python
import sys, json, time
from parakeet_mlx import from_pretrained
import mlx.core as mx

wav, out = sys.argv[1], sys.argv[2]
mx.set_cache_limit(512 * 2**20)
m = from_pretrained("mlx-community/parakeet-tdt-0.6b-v3")
t = time.monotonic()
mx.reset_peak_memory()
r = (
    m.transcribe(wav, chunk_duration=float(__import__("os").environ.get("CH", "120")), overlap_duration=15)
    if "--chunk" in sys.argv
    else m.transcribe(wav)
)
words = [{"w": t_.text, "start": round(t_.start, 2), "end": round(t_.end, 2)} for s in r.sentences for t_ in s.tokens]
json.dump(
    {"text": r.text, "tokens": words, "secs": time.monotonic() - t, "mlx_peak_gb": mx.get_peak_memory() / 1e9},
    open(out, "w"),
    ensure_ascii=False,
)
print("secs", time.monotonic() - t, "mlx_peak_gb", mx.get_peak_memory() / 1e9)
```

## run_whisper.py

```python
import sys, json, time
import mlx.core as mx, mlx_whisper

wav, out = sys.argv[1], sys.argv[2]
mx.set_cache_limit(512 * 2**20)
P = "Ну, э-э, вот, типа, короче, как бы, значит, слушайте... Я, ну, это, сейчас расскажу. Блин, ну."
S = dict(
    language="ru",
    word_timestamps=True,
    condition_on_previous_text=False,
    initial_prompt=P,
    hallucination_silence_threshold=2.0,
    no_speech_threshold=0.6,
    compression_ratio_threshold=2.4,
)
if "--noprompt" in sys.argv:
    S.pop("initial_prompt")
    S.pop("hallucination_silence_threshold")
if "--auto" in sys.argv:
    S.pop("language")
t = time.monotonic()
mx.reset_peak_memory()
r = mlx_whisper.transcribe(wav, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", **S)
words = [{"w": w["word"].strip(), "start": w["start"], "end": w["end"]} for s in r["segments"] for w in s.get("words", [])]
json.dump(
    {"text": r["text"], "words": words, "lang": r.get("language"), "secs": time.monotonic() - t, "mlx_peak_gb": mx.get_peak_memory() / 1e9},
    open(out, "w"),
    ensure_ascii=False,
)
print("secs", time.monotonic() - t, "mlx_peak_gb", mx.get_peak_memory() / 1e9, "lang", r.get("language"))
```

## run_sherpa.py

```python
import sys, json, time, wave, numpy as np, sherpa_onnx

wav, out = sys.argv[1], sys.argv[2]
d = "env/models/pk/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/"
r = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=d + "encoder.int8.onnx",
    decoder=d + "decoder.int8.onnx",
    joiner=d + "joiner.int8.onnx",
    tokens=d + "tokens.txt",
    model_type="nemo_transducer",
    num_threads=4,
)
w = wave.open(wav)
a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
t = time.monotonic()
res = []
step = 16000 * 60
for i in range(0, len(a), step):
    s = r.create_stream()
    s.accept_waveform(16000, a[i : i + step])
    r.decode_stream(s)
    res.append(s.result)
text = " ".join(x.text.strip() for x in res)
json.dump({"text": text, "secs": time.monotonic() - t}, open(out, "w"), ensure_ascii=False)
print("secs", time.monotonic() - t)
```

## emb.py

```python
import wave, numpy as np, sherpa_onnx, time, math, sys


def load(p, s, e):
    w = wave.open(p)
    w.setpos(int(s * 16000))
    return np.frombuffer(w.readframes(int((e - s) * 16000)), dtype=np.int16).astype(np.float32) / 32768


clips = {
    "solek_xb3_a": ("clips/xb3dwP46ZPk.wav", 20, 50),
    "solek_xb3_b": ("clips/xb3dwP46ZPk.wav", 300, 330),
    "solek_iS2": ("clips/iS2OorkuPoQ.wav", 100, 130),
    "th2o_spk0_a": ("clips/Th2O-5min.wav", 10, 40),
    "th2o_spk0_b": ("clips/Th2O-5min.wav", 200, 230),
    "th2o_spk1": ("clips/Th2O-5min.wav", 62, 90),
}
for name, model in [("wespeaker_en_resnet34", "env/models/wespk.onnx"), ("3dspeaker_eres2net", "env/models/w3d.onnx")]:
    t = time.monotonic()
    ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=model, num_threads=2))
    V = {}
    for k, (p, s, e) in clips.items():
        st = ex.create_stream()
        st.accept_waveform(16000, load(p, s, e))
        st.input_finished()
        v = np.array(ex.compute(st))
        V[k] = v / np.linalg.norm(v)
    print(name, "dim", len(v), "secs", round(time.monotonic() - t, 1))
    ks = list(V)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            print(f"  {ks[i]:12}{ks[j]:12}{float(V[ks[i]] @ V[ks[j]]):.3f}")
```

## diar_sherpa.py

```python
import sys, wave, time, numpy as np, sherpa_onnx

wav = sys.argv[1]
cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
    segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
        pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
            model="env/models/sherpa-onnx-pyannote-segmentation-3-0/model.onnx"
        ),
        num_threads=4,
    ),
    embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model="env/models/w3d.onnx", num_threads=4),
    clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=0.5),
    min_duration_on=0.3,
    min_duration_off=0.5,
)
sd = sherpa_onnx.OfflineSpeakerDiarization(cfg)
w = wave.open(wav)
a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
t = time.monotonic()
r = sd.process(a).sort_by_start_time()
segs = [(s.start, s.end, s.speaker) for s in r]
print("secs", round(time.monotonic() - t, 1), "speakers", len({s[2] for s in segs}), "segments", len(segs))
for s in segs[:12]:
    print(f"  spk{s[2]} {s[0]:.2f}-{s[1]:.2f}")
```

## cmp.py

```python
import json, re, difflib, sys

V = "/Users/iorlas/.local/share/channel-research/youtube/UCd190n-WQVHPC2l5gu0E2QQ/videos/"
PAT = {
    "ну": r"\bну\b",
    "э/эм/м-м": r"\b[эЭ]+(?:-э)*\b|\bэм+\b|\bм-м\b",
    "типа": r"\bтипа\b",
    "как бы": r"\bкак бы\b",
    "вот": r"\bвот\b",
    "короче": r"\bкороче\b",
}


def norm(t):
    return re.sub(r"[^\w\s]", "", re.sub(r"\s+-", "-", t.lower())).replace("ё", "е").split()


def load(vid):
    E = {}
    E["whisper(prompt)"] = " ".join(w["w"] for w in json.load(open(V + vid + "/transcript.local.json"))["words"])
    E["parakeet-mlx v3"] = json.load(open(f"out/parakeet_{vid}.json"))["text"]
    E["fluidaudio ultra"] = json.load(open(f"out/fa_ultra_{vid}.json"))["text"]
    try:
        E["sherpa v3 int8"] = json.load(open(f"out/sherpa_{vid}.json"))["text"]
    except Exception:
        pass
    return E


for vid in sys.argv[1:]:
    E = load(vid)
    print("==", vid)
    base = norm(E["parakeet-mlx v3"])
    for k, t in E.items():
        w = norm(t)
        r = difflib.SequenceMatcher(None, base, w, autojunk=False).ratio()
        c = {n: len(re.findall(p, t.lower().replace(" -", "-"))) for n, p in PAT.items()}
        print(f"{k:18}{len(w):6} words  agree_with_parakeet={r:.3f}  unk={t.count('<unk>')} субтитр={len(re.findall('убтитр', t))} {c}")
```

## bigruns.sh

```bash
cd $(dirname $0); F=fa/.build/release/fluidaudiocli
for c in iS2OorkuPoQ Th2O53gH-IA; do
 /usr/bin/time -l env/parakeet/bin/python run_parakeet.py clips/$c.wav out/parakeet_$c.json --chunk > out/parakeet_$c.txt 2>&1
 /usr/bin/time -l $F transcribe clips/$c.wav --model-version ultra --word-timestamps --output-json out/fa_ultra_$c.json > out/fa_ultra_$c.txt 2> out/fa_ultra_$c.err
 /usr/bin/time -l env/sherpa/bin/python run_sherpa.py clips/$c.wav out/sherpa_$c.json > out/sherpa_$c.txt 2>&1
done
echo done > out/bigruns.done
```
