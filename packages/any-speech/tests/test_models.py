from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from any_speech import CARDS, card_for, default_card
from any_speech.adapters import FluidAudioCli, FluidAudioDiarizer, ParakeetMlx, SherpaEmbedder

if TYPE_CHECKING:
    from pathlib import Path


def test_every_role_has_exactly_one_default() -> None:
    assert {r: sum(1 for c in CARDS if c.role == r and c.status == "default") for r in ("transcribe", "diarize", "embed")} == {
        "transcribe": 1,
        "diarize": 1,
        "embed": 1,
    }


def test_every_card_says_why_and_where_the_evidence_is() -> None:
    for c in CARDS:
        assert c.why.strip(), c.key
        assert c.evidence.strip(), c.key


def test_a_refused_or_untested_card_names_what_would_change_the_verdict() -> None:
    for c in CARDS:
        if c.status in ("refused", "untested"):
            assert c.revisit.strip(), c.key


def test_card_keys_are_unique() -> None:
    assert len({c.key for c in CARDS}) == len(CARDS)


def test_adapter_identities_match_their_cards(tmp_path: Path) -> None:
    binary = tmp_path / "fa"
    identities = [
        FluidAudioCli(binary, runtime="r", model_version="v3").identity,
        FluidAudioCli(binary, runtime="r", model_version="ultra").identity,
        FluidAudioDiarizer(binary, runtime="r").identity,
        ParakeetMlx(runtime="r").identity,
        SherpaEmbedder(tmp_path / "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx", runtime="r").identity,
    ]
    for ident in identities:
        assert card_for(ident.engine, ident.model).status in ("default", "available"), ident


def test_the_default_transcriber_card_is_parakeet_v3_through_fluidaudio() -> None:
    c = default_card("transcribe")
    assert (c.engine, c.model) == ("fluidaudio", "parakeet-tdt-0.6b-v3")


def test_an_unknown_model_has_no_card() -> None:
    with pytest.raises(KeyError):
        card_for("fluidaudio", "no-such-model")
