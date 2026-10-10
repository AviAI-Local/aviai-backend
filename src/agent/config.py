# src/agent/config.py
import os

# Val (RMIT's LLM gateway) is blocked from Render's network — requests get a
# 403 from RMIT's Azure Application Gateway before they even reach Val's app.
# Commented out rather than deleted so it's a one-line swap back once that's
# resolved (see session notes / lecturer thread).
# LLM_PROVIDER = os.getenv("LLM_PROVIDER", "val")
# LLM_MODEL = os.getenv("RMIT_VAL_MODEL", "anthropic-claude-sonnet-5")
# # Val's OpenAI-compatible base — keep the trailing slash, there is no /v1.
# LLM_BASE_URL = os.getenv("RMIT_VAL_BASE_URL", "https://val.rmit.edu.au/api/")
# LLM_API_KEY = os.getenv("RMIT_VAL_API_KEY")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
LLM_MODEL = os.getenv("OPENROUTER_MODEL_NAME", "openai/gpt-4o-mini")
LLM_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_API_KEY = os.getenv("OPENROUTER_API_KEY")

# "local" runs pocket_tts + faster-whisper in-process (needs real RAM/CPU —
# fine on a laptop or Docker locally, too much for Render's 512MB free tier).
# "openrouter" calls OpenRouter's hosted TTS/STT instead — use this on Render.
TTS_STT_PROVIDER = os.getenv("TTS_STT_PROVIDER", "local")

# "cosette" is a pocket_tts voice name; OpenRouter's deepgram/aura-2 model
# (see agent/io/tts/tts_openrouter.py) uses its own voice catalog instead.
_default_tts_voice = "cosette" if TTS_STT_PROVIDER == "local" else "aura-2-thalia-en"
TTS_VOICE = os.getenv("TTS_VOICE", _default_tts_voice)

# LLM_PROVIDER="lmstudio"
# LLM_MODEL="qwen/qwen3-vl-8b"
# LLM_BASE_URL="hhttp://localhost:1234/v1"