"""The engines. Each adapter imports its engine lazily, so installing one never requires another."""

from any_speech.adapters.fluidaudio import FluidAudioCli, FluidAudioDiarizer
from any_speech.adapters.parakeet_mlx import ParakeetMlx
from any_speech.adapters.sherpa_embed import SherpaEmbedder

__all__ = ["FluidAudioCli", "FluidAudioDiarizer", "ParakeetMlx", "SherpaEmbedder"]
