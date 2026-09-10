# src/agent/config.py
import os

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "val")
LLM_MODEL = os.getenv("RMIT_VAL_MODEL", "openai-gpt-5.2")
# Val's OpenAI-compatible base — keep the trailing slash, there is no /v1.
LLM_BASE_URL = os.getenv("RMIT_VAL_BASE_URL", "https://val.rmit.edu.au/api/")
LLM_API_KEY = os.getenv("RMIT_VAL_API_KEY")

# "cosette" was a pocket_tts voice name; OpenRouter's deepgram/aura-2 model
# (see agent/io/tts/tts_openrouter.py) uses its own voice catalog instead.
TTS_VOICE = os.getenv("TTS_VOICE", "aura-2-thalia-en")

# LLM_PROVIDER="lmstudio"
# LLM_MODEL="qwen/qwen3-vl-8b"
# LLM_BASE_URL="hhttp://localhost:1234/v1"