import json
import re
from langchain_core.runnables.history import RunnableWithMessageHistory

from agent.prompt.templates import STATIC_PROMPT
from rich.console import Console
from agent.model.response import LLMResponse

console = Console()

class LLMService:
    """
    High-level LLM service that handles:
    - history-aware invocation
    - session handling
    - output sanitization
    """

    def __init__(
        self,
        chat_chain: RunnableWithMessageHistory,
        session_id: str
    ):
        self.chat_chain = chat_chain
        self.session_id = session_id
    
    def parse_response(self, response: str) -> LLMResponse:
        """
        Parse and clean the LLM response.

        Args:
            response (str): raw LLM response
        """
        content = response.content if hasattr(response, "content") else str(response)
        content = re.sub(r"\s*\([^)]*\)\s*", " ", content).strip()
        cleaned = re.sub(r"```(?:json)?", "", content).replace("```", "").strip()

        data = json.loads(cleaned)
        llm_response = LLMResponse(**data)
        return llm_response


    def get_response(self, text: str) -> LLMResponse:
        """
        Generate a response from the LLM with conversation history.

        Args:
            text (str): user input

        Returns:
            str: cleaned assistant response
        """
        response = self.chat_chain.invoke(
            {"input": text},
            config={"session_id": self.session_id},
        )

        # response = re.sub(r"\s*\([^)]*\)\s*", " ", response).strip()

        # console.log(f"Raw LLM response: {response}")

        # content = response.content if hasattr(response, "content") else str(response)

        # content = re.sub(r"\s*\([^)]*\)\s*", " ", content).strip()

        llm_response = self.parse_response(response)
        # console.log(f"Parsed LLM response: {llm_response}")

        return llm_response

        