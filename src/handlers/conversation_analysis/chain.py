from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import json
from .model import LLMEmotionAnalysisOutput

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

llm = ChatOllama(
    model="gemma3",
    base_url="http://localhost:11434",
    temperature=0.3,
    format="json"
)

async def analyze_conversation(inputs: dict) -> LLMEmotionAnalysisOutput:
    raw = await (prompt | llm).ainvoke(inputs)

    data = json.loads(raw.content)

    if "analysis" not in data:
        raise ValueError(f"Invalid LLM output schema: {data}")

    return LLMEmotionAnalysisOutput(**data)
