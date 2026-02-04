from langchain_ollama import ChatOllama
from agent.config import LLM_MODEL, LLM_BASE_URL


def get_llm(temperature: float = 0.3, format: str = "json") -> ChatOllama:
    return ChatOllama(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        temperature=temperature,
        format=format,
    )
