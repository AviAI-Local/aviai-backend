# src/agent/config.py
import os

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
LLM_MODEL = os.getenv("OPENROUTER_MODEL_NAME", "openai/gpt-4o-mini")
LLM_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_API_KEY = os.getenv("OPENROUTER_API_KEY")

STT_MODEL = os.getenv("OPENROUTER_STT_MODEL", "openai/whisper-large-v3")
TTS_MODEL = os.getenv("OPENROUTER_TTS_MODEL", "deepgram/aura-2")
TTS_VOICE = os.getenv("TTS_VOICE", "aura-2-thalia-en")
TTS_SAMPLE_RATE = int(os.getenv("OPENROUTER_TTS_SAMPLE_RATE", "24000"))


# LLM_PROVIDER="lmstudio"
# LLM_MODEL="qwen/qwen3-vl-8b"
# LLM_BASE_URL="hhttp://localhost:1234/v1"