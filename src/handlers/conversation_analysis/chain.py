from langchain_core.prompts import ChatPromptTemplate
import json

from .llm import get_llm
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

def get_emotion_analysis_chain():
    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{conversation_data}"),
        ]
    )

    return prompt | llm


async def analyze_conversation(inputs: dict) -> LLMEmotionAnalysisOutput:
    chain = get_emotion_analysis_chain()
    raw = await chain.ainvoke(inputs)

    data = json.loads(raw.content)

    if "analysis" not in data:
        raise ValueError(f"Invalid LLM output schema: {data}")

    return LLMEmotionAnalysisOutput(**data)
