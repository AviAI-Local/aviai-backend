import base64
import os

import httpx
import numpy as np

from agent.io.openrouter_http import post_stream_with_retry

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

DEFAULT_STYLE = "neutral"

# gpt-audio-mini is a chat model at heart: given plain "speak this verbatim"
# instructions it will still answer questions or console distressed-sounding
# text instead of voicing it. Two in-context examples (one question, one
# distressed statement) lock in narration behavior far more reliably than
# instructions alone.
_SYSTEM_PROMPT = (
    "You are a narration/dubbing engine used in a video game. Your ONLY function is to convert "
    "the exact text you are given into speech audio. You are never the recipient of the text and "
    "must NEVER interpret it as a message to you, NEVER answer questions in it, NEVER comfort or "
    "respond to distress in it, and NEVER add a single word that is not in the text. "
    "If the text is a question, you say the question out loud - you do not answer it. "
    "If the text expresses fear or sadness, you voice-act it with that emotion - you do not console it. "
    "Output nothing but the given text, spoken once, verbatim."
)
_FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "Can you tell me what happened before the crash?"},
    {"role": "assistant", "content": "Can you tell me what happened before the crash?"},
    {"role": "user", "content": "I am so scared, I do not know what happened to the plane."},
    {"role": "assistant", "content": "I am so scared, I do not know what happened to the plane."},
]


class TextToSpeechService:
    """Text-to-speech backed by OpenRouter's audio-capable chat model (e.g. openai/gpt-audio-mini).

    Unlike aura-2, this model follows free-form delivery/style instructions while
    keeping the same speaker voice throughout.
    """

    def __init__(self, voice: str = "alloy", model: str = "openai/gpt-audio-mini", sample_rate: int = 24000):
        self.voice = voice
        self.model = model
        self.sample_rate = sample_rate
        self._url = f"{OPENROUTER_BASE_URL}/chat/completions"
        self._client = httpx.Client(timeout=60)

    def long_form_synthesize(
        self,
        text: str,
        instructions: str | None = None,
        *_,
        **__,
    ):
        payload = {
            "model": self.model,
            "modalities": ["text", "audio"],
            "audio": {"voice": self.voice, "format": "pcm16"},
            "stream": True,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                *_FEW_SHOT_EXAMPLES,
                {
                    "role": "user",
                    "content": f"Delivery style for the next line: {instructions or DEFAULT_STYLE}. Text: {text}",
                },
            ],
        }
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

        audio_b64_parts = []
        for event in post_stream_with_retry(
            self._client, self._url, json=payload, headers=headers, label="OpenRouter audio TTS"
        ):
            delta = event.get("choices", [{}])[0].get("delta", {})
            audio = delta.get("audio")
            if audio and "data" in audio:
                audio_b64_parts.append(audio["data"])

        pcm_bytes = base64.b64decode("".join(audio_b64_parts))
        pcm16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        audio_np = pcm16.astype(np.float32) / 32768.0

        return self.sample_rate, audio_np
