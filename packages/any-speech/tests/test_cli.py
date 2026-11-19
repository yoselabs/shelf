from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from any_speech import Pipeline, Transcript, Word
from any_speech.cli import Settings, main
from any_speech.testing import FakeEmbedder, FakeTranscriber

if TYPE_CHECKING:
    import pytest


def _build(_s: Settings) -> Pipeline:
    return Pipeline(FakeTranscriber((Word("да", 0.0, 0.5),)), None, probe=lambda _p: 1.0)


def _lock(tmp_path: Path):
    return lambda: tmp_path / "leases"


def test_transcribe_writes_the_json_beside_the_audio(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    assert main(["transcribe", str(audio), "--engine", "fluidaudio"], build=_build, leases_root=_lock(tmp_path)) == 0
    assert Transcript.load(tmp_path / "a.m4a.speech.json").text == "да"
    assert capsys.readouterr().out.strip().endswith("a.m4a.speech.json")


def test_drain_transcribes_a_folder_and_reports_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for name in ("v1", "v2"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "audio.m4a").write_bytes(name.encode())
    assert main(["drain", str(tmp_path), "--engine", "fluidaudio"], build=_build, leases_root=_lock(tmp_path)) == 0
    assert json.loads(capsys.readouterr().out) == {"done": 2, "failed": 0, "skipped": 0}
    assert (tmp_path / "v1" / "speech.json").exists()
    assert main(["drain", str(tmp_path), "--engine", "fluidaudio"], build=_build, leases_root=_lock(tmp_path)) == 0
    assert json.loads(capsys.readouterr().out)["done"] == 0


def test_drain_exits_non_zero_when_a_file_failed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "audio.m4a").write_bytes(b"bad")
    broken = lambda _s: Pipeline(FakeTranscriber((), fail_on=b"bad"), None, probe=lambda _p: 1.0)  # noqa: E731
    assert main(["drain", str(tmp_path), "--engine", "fluidaudio"], build=broken, leases_root=_lock(tmp_path)) == 1
    assert json.loads(capsys.readouterr().out)["failed"] == 1


def test_embed_then_match_prints_the_similarity(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host, other = tmp_path / "host.wav", tmp_path / "other.wav"
    host.write_bytes(b"h")
    other.write_bytes(b"o")
    embedder = lambda _s: FakeEmbedder({"host.wav": (1.0, 0.0), "other.wav": (0.6, 0.8)})  # noqa: E731
    saved = tmp_path / "host.voice.json"
    assert main(["embed", str(host), "--out", str(saved), "--engine", "fluidaudio"], embedder=embedder) == 0
    assert json.loads(saved.read_text()) == {"model": "fake-embedder", "vector": [1.0, 0.0]}
    assert main(["match", str(other), "--voice", str(saved), "--engine", "fluidaudio"], embedder=embedder) == 0
    assert capsys.readouterr().out.strip() == "0.6000"


def _script(*args: str) -> subprocess.CompletedProcess[str]:
    script = Path(sys.executable).parent / "any-speech"
    return subprocess.run([str(script), *args], capture_output=True, text=True, check=False)


def test_help_answers_and_changes_nothing(tmp_path: Path) -> None:
    before = sorted(tmp_path.iterdir())
    done = _script("--help")
    assert (done.returncode, "drain" in done.stdout) == (0, True)
    assert sorted(tmp_path.iterdir()) == before


def test_an_unknown_flag_exits_2() -> None:
    assert _script("transcribe", "a.wav", "--engine", "fluidaudio", "--no-such-flag").returncode == 2
