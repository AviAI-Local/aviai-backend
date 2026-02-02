import httpx
import re
from .model import DocumentLLMResp

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:latest"

SYSTEM_PROMPT = """
You are Usecase-DocExtractor.

Extract and return STRICT JSON with:
- usecase_name
- usecase_summary
- character_name
- gender (male or female)

No extra text. No markdown.
"""


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
        "prompt": f"{SYSTEM_PROMPT}\n\n{text}",
        "stream": False,
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
