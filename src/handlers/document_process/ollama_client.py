import os
import httpx
import re
from .schema import DocumentLLMResp

OLLAMA_BASE_URL = os.environ.get("OLLAMA_MODEL_URL")
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
MODEL = os.environ.get("OLLAMA_MODEL_NAME")

SYSTEM_PROMPT = """You are scenario-DocExtractor. You extract metadata from documents.
You MUST return a JSON object with exactly these fields:
- "scenario_name": a short name for the scenario
- "scenario_summary": a brief summary of the scenario
- "character_name": the name of the main character
- "gender": "male" or "female"

Return ONLY the JSON object. No extra text."""


def _strip_markdown_json(text: str) -> str:
    """
    Removes ```json ... ``` fences if the model ignores instructions.
    """
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    return text.strip()


async def extract_metadata(text: str) -> DocumentLLMResp:
    payload = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": f"Extract metadata from the following document:\n\n{text}",
        "stream": False,
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(OLLAMA_URL, json=payload)
        r.raise_for_status()

    data = r.json()

    # Ollama returns the full response here
    raw_content = data["response"]

    # ✅ CRITICAL FIX
    clean_json = _strip_markdown_json(raw_content)

    return DocumentLLMResp.model_validate_json(clean_json)
