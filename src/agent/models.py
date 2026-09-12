"""
Singleton module for pre-loaded ML models (TTS, STT).
Models are loaded once at app startup to avoid delays during WebSocket connections.
"""

from rich.console import Console
from agent.config import TTS_VOICE, TTS_STT_PROVIDER

console = Console()

# Global model instances
_tts_instance = None
_stt_instance = None


def init_models():
    """Initialize TTS and STT clients. Call this at app startup.

    Provider is chosen by TTS_STT_PROVIDER (see agent/config.py):
    "local" loads torch/faster-whisper models in-process (needs real
    RAM/CPU); "openrouter" calls OpenRouter's hosted audio endpoints
    instead, which is what Render's free tier (512MB cap) needs.
    """
    global _tts_instance, _stt_instance

    console.print(f"[cyan]Loading TTS client ({TTS_STT_PROVIDER})...[/cyan]")
    if TTS_STT_PROVIDER == "local":
        from agent.io.tts.tts_pocket import TextToSpeechService
    else:
        from agent.io.tts.tts_openrouter import TextToSpeechService
    _tts_instance = TextToSpeechService(voice=TTS_VOICE)
    console.print("[green]✓ TTS client ready[/green]")

    console.print(f"[cyan]Loading STT client ({TTS_STT_PROVIDER})...[/cyan]")
    if TTS_STT_PROVIDER == "local":
        from agent.io.stt.faster_whisper import FasterWhisperSTT
        _stt_instance = FasterWhisperSTT(
            model_size="small",
            silence_db=-45,
            end_silence_sec=1.2,
        )
    else:
        from agent.io.stt.openrouter_stt import OpenRouterSTT
        _stt_instance = OpenRouterSTT()
    console.print("[green]✓ STT client ready[/green]")


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
