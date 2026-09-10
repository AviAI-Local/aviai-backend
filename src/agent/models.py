"""
Singleton module for pre-loaded ML models (TTS, STT).
Models are loaded once at app startup to avoid delays during WebSocket connections.
"""

import os

from rich.console import Console
from agent.config import TTS_VOICE

console = Console()

# "openrouter" (default) calls hosted STT/TTS over HTTP - no model weights loaded
# in-process, which is required to fit Render's 512MB free-tier RAM budget and to
# let uvicorn bind its port before the deploy's health check times out. "local"
# loads faster-whisper + pocket-tts on-device (torch/ctranslate2, GBs of RAM) for
# dev boxes that have the RAM and want offline inference.
STT_PROVIDER = os.getenv("STT_PROVIDER", "openrouter")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openrouter")

# Global model instances
_tts_instance = None
_stt_instance = None


def init_models():
    """Initialize TTS and STT models. Call this at app startup."""
    global _tts_instance, _stt_instance

    console.print(f"[cyan]Loading TTS model (provider={TTS_PROVIDER})...[/cyan]")
    if TTS_PROVIDER == "local":
        from agent.io.tts.tts_pocket import TextToSpeechService
        _tts_instance = TextToSpeechService(voice=TTS_VOICE)
    else:
        from agent.io.tts.tts_openrouter import TextToSpeechService
        _tts_instance = TextToSpeechService()
    console.print("[green]✓ TTS model loaded[/green]")

    console.print(f"[cyan]Loading STT model (provider={STT_PROVIDER})...[/cyan]")
    if STT_PROVIDER == "local":
        from agent.io.stt.faster_whisper import FasterWhisperSTT
        _stt_instance = FasterWhisperSTT(
            model_size="small",
            silence_db=-45,
            end_silence_sec=1.2,
        )
    else:
        from agent.io.stt.openrouter_stt import OpenRouterSTT
        _stt_instance = OpenRouterSTT()
    console.print("[green]✓ STT model loaded[/green]")


def get_tts():
    """Get the shared TTS instance."""
    if _tts_instance is None:
        raise RuntimeError("TTS model not initialized. Call init_models() first.")
    return _tts_instance


def get_stt():
    """Get the shared STT instance."""
    if _stt_instance is None:
        raise RuntimeError("STT model not initialized. Call init_models() first.")
    return _stt_instance
