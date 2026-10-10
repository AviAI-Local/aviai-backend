import os

import httpx
import numpy as np

from agent.io.openrouter_http import post_with_retry

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")


class TextToSpeechService:
    """Text-to-speech backed by OpenRouter's /audio/speech endpoint."""

    def __init__(self, voice: str = "aura-2-thalia-en", model: str = "deepgram/aura-2", sample_rate: int = 24000):
        self.voice = voice
        self.model = model
        self.sample_rate = sample_rate
        self._url = f"{OPENROUTER_BASE_URL}/audio/speech"
        self._client = httpx.Client(timeout=60)

    def long_form_synthesize(
        self,
        text: str,
        voice: str | None = None,
        *_,
        **__,
    ):
        payload = {
            "model": self.model,
            "input": text,
            "voice": voice or self.voice,
            "response_format": "pcm",
        }
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

        r = post_with_retry(self._client, self._url, json=payload, headers=headers, label="OpenRouter TTS")

        pcm16 = np.frombuffer(r.content, dtype=np.int16)
        audio_np = pcm16.astype(np.float32) / 32768.0

        return self.sample_rate, audio_np
