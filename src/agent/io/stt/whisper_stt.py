import numpy as np
import whisper
from rich.console import Console

console = Console()

class WhisperSTT:
    """
    Wrapper around OpenAI Whisper for speech-to-text.
    Loads the model once and reuses it.
    """

    def __init__(self, model_name: str = "base.en", fp16: bool = False):
        console.print(f"[dim]Loading Whisper model: {model_name}[/dim]")
        self.model = whisper.load_model(model_name)
        self.fp16 = fp16

    def transcribe(self, audio_np: np.ndarray) -> str:
        """
        Transcribe audio numpy array into text.

        Args:
            audio_np (np.ndarray): float32 PCM audio (-1.0 to 1.0)

        Returns:
            str: Transcribed text
        """
        if audio_np.size == 0:
            return ""

        result = self.model.transcribe(
            audio_np,
            fp16=self.fp16,
        )

        return result.get("text", "").strip()