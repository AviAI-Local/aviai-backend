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
    """Initialize TTS and STT models. Call this at app startup."""
    global _tts_instance, _stt_instance

    console.print("[cyan]Loading TTS model...[/cyan]")
    from agent.io.tts.tts_pocket import TextToSpeechService
    _tts_instance = TextToSpeechService()
    console.print("[green]✓ TTS model loaded[/green]")

    console.print("[cyan]Loading STT model...[/cyan]")
    from agent.io.stt.faster_whisper import FasterWhisperSTT
    _stt_instance = FasterWhisperSTT(
        model_size="small",
        silence_db=-45,
        end_silence_sec=1.2,
    )
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
