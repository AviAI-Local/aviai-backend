from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import re
from agent.config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY
from .model import LLMEmotionAnalysisOutput


def _strip_markdown_json(text: str) -> str:
    """Val ignores response_format=json_object and may fence its JSON output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()

SYSTEM_PROMPT = """
You are an expert conversation analyst specializing in emotion analysis.

You MUST return valid JSON in this EXACT structure:

{{
  "analysis": [
    {{
      "user_emotion_analysis": "string"
    }}
  ]
}}

Rules:
- The top-level key MUST be "analysis"
- Do NOT rename keys
- Do NOT add extra keys
- Do NOT wrap in markdown
- Do NOT return explanations
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),          # ← SYSTEM PROMPT GOES HERE
        ("human", "{conversation_data}")    # ← runtime input
    ]
)

# Val silently ignores response_format={"type":"json_object"}; the prompt's
# strict JSON instructions + _strip_markdown_json() below carry the load instead.
llm = ChatOpenAI(
    model=LLM_MODEL,
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
    temperature=0.3,
)

async def analyze_conversation(inputs: dict) -> LLMEmotionAnalysisOutput:
    raw = await (prompt | llm).ainvoke(inputs)

    data = json.loads(_strip_markdown_json(raw.content))

    if "analysis" not in data:
        raise ValueError(f"Invalid LLM output schema: {data}")

    return LLMEmotionAnalysisOutput(**data)
