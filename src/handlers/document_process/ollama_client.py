import httpx
import re
from agent.config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY
from .schema import DocumentLLMResp

VAL_CHAT_URL = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"

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
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract metadata from the following document:\n\n{text}"},
        ],
        "stream": False,
        # response_format=json_object is silently ignored on Val; _strip_markdown_json
        # below handles the fenced prose it returns instead.
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(VAL_CHAT_URL, json=payload, headers=headers)
        r.raise_for_status()

    data = r.json()

    raw_content = data["choices"][0]["message"]["content"]

    # ✅ CRITICAL FIX
    clean_json = _strip_markdown_json(raw_content)

    return DocumentLLMResp.model_validate_json(clean_json)
