# src/agent/config.py
import os

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("OLLAMA_MODEL_NAME", "gemma3")
LLM_BASE_URL = os.getenv("OLLAMA_MODEL_URL", "http://localhost:11434")

TTS_VOICE = os.getenv("TTS_VOICE", "cosette")


# LLM_PROVIDER="lmstudio"
# LLM_MODEL="qwen/qwen3-vl-8b"
# LLM_BASE_URL="hhttp://localhost:1234/v1"