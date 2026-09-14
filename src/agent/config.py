# src/agent/config.py
import os

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "val")
LLM_MODEL = os.getenv("RMIT_VAL_MODEL", "openai-gpt-5.2")
# Val's OpenAI-compatible base — keep the trailing slash, there is no /v1.
LLM_BASE_URL = os.getenv("RMIT_VAL_BASE_URL", "https://val.rmit.edu.au/api/")
LLM_API_KEY = os.getenv("RMIT_VAL_API_KEY")

# "local" runs pocket_tts + faster-whisper in-process (needs real RAM/CPU —
# fine on a laptop or Docker locally, too much for Render's 512MB free tier).
# "openrouter" calls OpenRouter's hosted aura-2 TTS + whisper STT instead.
# "openrouter-audio" uses OpenRouter's gpt-audio-mini for TTS instead of
# aura-2: one fixed speaker voice that actually follows delivery/emotion
# instructions (aura-2 can only swap to a different persona, it has no
# style control). STT still goes through OpenRouter's whisper endpoint.
TTS_STT_PROVIDER = os.getenv("TTS_STT_PROVIDER", "local")

# Voice name meaning depends on the provider: a pocket_tts catalog name for
# "local", an aura-2 voice for "openrouter", an OpenAI-style voice name
# (e.g. "alloy") for "openrouter-audio".
_default_tts_voice = {
    "local": "cosette",
    "openrouter": "aura-2-thalia-en",
    "openrouter-audio": "alloy",
}.get(TTS_STT_PROVIDER, "cosette")
TTS_VOICE = os.getenv("TTS_VOICE", _default_tts_voice)
OPENROUTER_AUDIO_MODEL = os.getenv("OPENROUTER_AUDIO_MODEL", "openai/gpt-audio-mini")

# LLM_PROVIDER="lmstudio"
# LLM_MODEL="qwen/qwen3-vl-8b"
# LLM_BASE_URL="hhttp://localhost:1234/v1"