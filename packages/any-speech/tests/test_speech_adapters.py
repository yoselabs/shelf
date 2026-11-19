"""Each adapter against the output its engine really produced (recorded 2026-11-19), with the engine faked at its edge."""

from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from any_speech import MemoryBudgetError, Piece, Voice
from any_speech.adapters import FluidAudioCli, FluidAudioDiarizer, ParakeetMlx, SherpaEmbedder
from any_speech.adapters._child import ChildResult, run_child
from any_speech.adapters.fluidaudio import FluidAudioError, parse_rttm

# fluidaudiocli 0b1f4628, `transcribe --word-timestamps --output-json`, Solek xb3dwP46ZPk (first words; Ultra added <unk>).
_FLUID_JSON = {
    "wordTimings": [
        {"confidence": 0.64, "endTime": 7.76, "startTime": 7.28, "word": "<unk>п"},
        {"confidence": 0.999, "endTime": 8.16, "startTime": 7.76, "word": "твою"},
        {"confidence": 0.81, "endTime": 8.64, "startTime": 8.16, "word": "мать,"},
        {"confidence": 1.0, "endTime": 8.7, "startTime": 8.65, "word": "<unk>"},
    ]
}
# `nemotron3-diarize --output`, a 5 minute clip: two voices, out of order on purpose.
_RTTM = """SPEAKER Th2O-5min 1 59.800 31.100 <NA> <NA> speaker_1 <NA> <NA>
SPEAKER Th2O-5min 1 0.720 59.020 <NA> <NA> speaker_0 <NA> <NA>
SPEAKER Th2O-5min 1 90.960 63.120 <NA> <NA> speaker_0 <NA> <NA>
"""


def _runner(write: dict[str, str], *, code: int = 0, peak: float = 0.5) -> Any:
    seen: list[list[str]] = []

    def run(args: Any, *, timeout: float | None, budget_gb: float | None = None) -> ChildResult:
        argv = [str(a) for a in args]
        seen.append(argv)
        for flag, body in write.items():
            Path(argv[argv.index(flag) + 1]).write_text(body, encoding="utf-8")
        return ChildResult(code, 2.0, peak, "boom on stderr" if code else "")

    run.seen = seen  # type: ignore[attr-defined]  # test spy
    return run


def test_fluidaudio_words_drop_the_unk_placeholder_and_keep_confidence(tmp_path: Path) -> None:
    run = _runner({"--output-json": json.dumps(_FLUID_JSON)})
    heard = FluidAudioCli(Path("fa"), runtime="fluidaudio-0.17.5", model_version="ultra", run=run).transcribe(tmp_path / "a.wav")
    assert [(w.text, w.start, w.probability) for w in heard.words] == [("п", 7.28, 0.64), ("твою", 7.76, 0.999), ("мать,", 8.16, 0.81)]
    assert (heard.seconds, heard.peak_memory_gb) == (2.0, 0.5)
    assert run.seen[0][1:2] == ["transcribe"]
    assert run.seen[0][run.seen[0].index("--model-version") + 1] == "ultra"


def test_fluidaudio_states_model_and_runtime() -> None:
    ident = FluidAudioCli(Path("fa"), runtime="fluidaudio-0.17.5", model_version="v3").identity
    assert (ident.engine, ident.model, ident.runtime) == ("fluidaudio", "parakeet-tdt-0.6b-v3", "fluidaudio-0.17.5")


def test_a_failing_binary_is_an_error_with_its_stderr(tmp_path: Path) -> None:
    with pytest.raises(FluidAudioError, match="boom on stderr"):
        FluidAudioCli(Path("fa"), runtime="r", run=_runner({}, code=3)).transcribe(tmp_path / "a.wav")


def test_rttm_becomes_turns_labelled_by_first_appearance() -> None:
    turns = parse_rttm(_RTTM)
    assert [(t.label, t.start) for t in turns] == [("S1", 0.72), ("S2", 59.8), ("S1", 90.96)]
    assert turns[0].end == pytest.approx(59.74)


def test_fluidaudio_diarizer_reads_the_rttm_it_asked_for(tmp_path: Path) -> None:
    run = _runner({"--output": _RTTM})
    diarized = FluidAudioDiarizer(Path("fa"), runtime="r", run=run).diarize(tmp_path / "a.wav")
    assert len(diarized.turns) == 3
    assert run.seen[0][1:2] == ["nemotron3-diarize"]


def test_run_child_reports_exit_code_and_its_own_peak() -> None:
    ok = run_child(["python3", "-c", "x = bytearray(60_000_000); print(len(x))"], timeout=30)
    assert (ok.returncode, ok.peak_gb > 0.05) == (0, True)
    bad = run_child(["python3", "-c", "import sys; sys.stderr.write('nope'); sys.exit(4)"], timeout=30)
    assert (bad.returncode, bad.stderr_tail) == (4, "nope")


def test_run_child_kills_a_child_past_its_timeout() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        run_child(["python3", "-c", "import time; time.sleep(30)"], timeout=0.3)


def test_run_child_kills_a_child_that_grows_past_the_budget_before_it_finishes() -> None:
    code = "import time; x = bytearray(400_000_000); x[::4096] = b'1' * len(x[::4096]); time.sleep(30)"
    started = time.monotonic()
    with pytest.raises(MemoryBudgetError, match="budget"):
        run_child(["python3", "-c", code], timeout=60, budget_gb=0.2)
    assert time.monotonic() - started < 10


def test_run_child_leaves_no_process_behind_after_a_budget_kill(tmp_path: Path) -> None:
    from stream_proc import group_alive  # noqa: PLC0415

    inner = "import time; x = bytearray(400_000_000); x[::4096] = b'1' * len(x[::4096]); time.sleep(30)"
    mark = tmp_path / "pgid"
    code = (
        f"import os, subprocess, sys, time; open({str(mark)!r}, 'w').write(str(os.getpgrp())); "
        f"subprocess.Popen([sys.executable, '-c', {inner!r}]); time.sleep(30)"
    )
    with pytest.raises(MemoryBudgetError):
        run_child(["python3", "-c", code], timeout=60, budget_gb=0.2)
    pgid = int(mark.read_text())
    deadline = time.monotonic() + 3  # a killed member is a zombie until init reaps it
    while group_alive(pgid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not group_alive(pgid)


def test_run_child_counts_the_children_of_the_child() -> None:
    inner = "import time; x = bytearray(400_000_000); x[::4096] = b'1' * len(x[::4096]); time.sleep(30)"
    code = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {inner!r}]); time.sleep(30)"
    with pytest.raises(MemoryBudgetError):
        run_child(["python3", "-c", code], timeout=60, budget_gb=0.2)


def test_fluidaudio_passes_its_budget_to_the_runner(tmp_path: Path) -> None:
    seen: list[float | None] = []

    def spy(args: Any, *, timeout: float | None, budget_gb: float | None) -> ChildResult:
        seen.append(budget_gb)
        argv = [str(a) for a in args]
        Path(argv[argv.index("--output-json") + 1]).write_text(json.dumps(_FLUID_JSON), encoding="utf-8")
        return ChildResult(0, 1.0, 0.1, "")

    FluidAudioCli(Path("fa"), runtime="r", budget_gb=1.5, run=spy).transcribe(tmp_path / "a.wav")
    assert seen == [1.5]


class _Mem:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def cap(self, megabytes: int) -> None:
        self.calls.append(f"cap {megabytes}")

    def reset_peak(self) -> None:
        self.calls.append("reset")

    def peak_gb(self) -> float:
        return 3.2

    def clear(self) -> None:
        self.calls.append("clear")


def test_parakeet_joins_subword_tokens_chunks_and_caps_the_cache(tmp_path: Path) -> None:
    token = lambda text, start, end: SimpleNamespace(text=text, start=start, end=end)  # noqa: E731
    sentence = SimpleNamespace(tokens=[token(" Про", 1.0, 1.2), token("сто", 1.2, 1.5), token(".", 1.5, 1.6), token(" Да", 1.7, 1.9)])
    asked: dict[str, Any] = {}

    class Model:
        def transcribe(self, path: str, **kw: float) -> Any:
            asked.update(kw)
            return SimpleNamespace(sentences=[sentence])

    mem = _Mem()
    loads: list[str] = []
    adapter = ParakeetMlx(runtime="parakeet-mlx-0.7.0", loader=lambda m: loads.append(m) or Model(), memory=lambda: mem)
    heard = adapter.transcribe(tmp_path / "a.wav")
    adapter.transcribe(tmp_path / "a.wav")
    assert [w.text for w in heard.words] == ["Просто.", "Да"]
    assert asked == {"chunk_duration": 120.0, "overlap_duration": 15.0}
    assert (heard.peak_memory_gb, mem.calls[:3], len(loads)) == (3.2, ["cap 512", "reset", "clear"], 1)


def test_parakeet_never_runs_two_calls_at_once_on_its_shared_model(tmp_path: Path) -> None:
    inside = 0
    most = 0

    class Model:
        def transcribe(self, path: str, **kw: float) -> Any:
            nonlocal inside, most
            inside += 1
            most = max(most, inside)
            time.sleep(0.05)
            inside -= 1
            return SimpleNamespace(sentences=[])

    adapter = ParakeetMlx(runtime="r", loader=lambda _m: Model(), memory=_Mem)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: adapter.transcribe(tmp_path / "a.wav"), range(4)))
    assert most == 1


def test_embedder_returns_a_unit_vector_named_for_its_model(tmp_path: Path) -> None:
    class Stream:
        def accept_waveform(self, rate: int, samples: list[float]) -> None:
            self.n = len(samples)

        def input_finished(self) -> None: ...

    class Extractor:
        def create_stream(self) -> Stream:
            return Stream()

        def compute(self, stream: Stream) -> list[float]:
            return [3.0, 4.0]

    embedder = SherpaEmbedder(
        Path("m/3dspeaker.onnx"), runtime="sherpa-onnx-2.0.2", extractor=lambda _m: Extractor(), decode=lambda *_a: [0.0] * 16000
    )
    voice = embedder.embed(tmp_path / "a.wav", start=1.0, end=2.0)
    assert voice == Voice("3dspeaker", (0.6, 0.8))


def test_voices_compare_by_dot_product_and_refuse_other_models() -> None:
    a, b = Voice("m", (1.0, 0.0)), Voice("m", (0.6, 0.8))
    assert a.similarity(b) == pytest.approx(0.6)
    with pytest.raises(ValueError, match="different models"):
        a.similarity(Voice("n", (1.0, 0.0)))


def test_piece_is_public() -> None:
    assert Piece(" a", 0.0, 1.0).probability is None
