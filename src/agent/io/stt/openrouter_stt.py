import base64
import io
import os
import wave

import httpx
import numpy as np

from agent.io.openrouter_http import post_with_retry

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")


class OpenRouterSTT:
    """Speech-to-text backed by OpenRouter's /audio/transcriptions endpoint."""

    def __init__(self, model: str = "openai/whisper-large-v3", samplerate: int = 16000, language: str = "en"):
        self.model = model
        self.samplerate = samplerate
        self.language = language
        self._url = f"{OPENROUTER_BASE_URL}/audio/transcriptions"
        self._client = httpx.Client(timeout=60)

    def _encode_wav(self, audio_data: np.ndarray) -> str:
        pcm16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.samplerate)
            wf.writeframes(pcm16.tobytes())
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def transcribe(self, audio_data: np.ndarray) -> str:
        payload = {
            "model": self.model,
            "input_audio": {
                "data": self._encode_wav(audio_data),
                "format": "wav",
            },
            "language": self.language,
        }
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

        r = post_with_retry(self._client, self._url, json=payload, headers=headers, label="OpenRouter STT")

        return r.json().get("text", "").strip()
