import os
import httpx
import re
from .schema import DocumentLLMResp

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_URL = f"{OPENROUTER_BASE_URL}/chat/completions"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = os.environ.get("OPENROUTER_MODEL_NAME", "openai/gpt-4o-mini")

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
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract metadata from the following document:\n\n{text}"},
        ],
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        r.raise_for_status()

    data = r.json()

    raw_content = data["choices"][0]["message"]["content"]

    # ✅ CRITICAL FIX
    clean_json = _strip_markdown_json(raw_content)

    return DocumentLLMResp.model_validate_json(clean_json)
