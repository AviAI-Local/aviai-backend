"""
Singleton module for pre-loaded ML models (TTS, STT).
Models are loaded once at app startup to avoid delays during WebSocket connections.
"""

from rich.console import Console
from agent.config import TTS_VOICE

console = Console()

# Global model instances
_tts_instance = None
_stt_instance = None


def init_models():
    """Initialize TTS and STT clients. Call this at app startup.

    Uses OpenRouter's hosted audio endpoints rather than loading local
    torch/faster-whisper models in-process — Render's free tier caps
    instances at 512MB, which local model weights alone exceed.
    """
    global _tts_instance, _stt_instance

    console.print("[cyan]Loading TTS client...[/cyan]")
    from agent.io.tts.tts_openrouter import TextToSpeechService
    _tts_instance = TextToSpeechService(voice=TTS_VOICE)
    console.print("[green]✓ TTS client ready[/green]")

    console.print("[cyan]Loading STT client...[/cyan]")
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
