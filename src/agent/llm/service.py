import json
import re
from langchain_core.runnables.history import RunnableWithMessageHistory

from agent.prompt.templates import STATIC_PROMPT
from rich.console import Console
from agent.llm.schema import LLMResponse

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
        default_response = LLMResponse(
            response="I'm sorry, I didn't quite understand that. Could you please repeat?",
            avatar_instructions="neutral",
            voice_instructions="neutral"
        )

        try:
            # 1. Extract content safely
            content = response.content if hasattr(response, "content") else str(response)

            # 2. Remove parenthetical asides (e.g. (laughs), (pause))
            content = re.sub(r"\s*\([^)]*\)\s*", " ", content).strip()

            # 3. Remove markdown code fences
            cleaned = re.sub(r"```(?:json)?", "", content).replace("```", "").strip()

            # 4. Fix newlines and control characters in JSON strings
            # Replace literal newlines within the content with spaces
            cleaned = cleaned.replace('\n', ' ')
            # Normalize multiple spaces to single space
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()

            # 5. Attempt JSON parsing
            data = json.loads(cleaned)

            # 6. Validate required keys (important!)
            if not isinstance(data, dict):
                raise ValueError("Parsed JSON is not an object")

            if "response" not in data:
                raise KeyError("Missing 'response' field")

            # 7. Fill optional fields safely
            data.setdefault("avatar_instructions", "neutral")

            return LLMResponse(**data)

        except Exception as e:
            # Log for debugging
            # if hasattr(response, "content"):
                # console.log(f"[yellow]Response content: {response.content}[/yellow]")
            return default_response


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

        # console.log(f"[cyan]Raw LLM response: {response}[/cyan]")

        # if hasattr(response, "content"):
            # console.log(f"[cyan]Response content: {response.content}[/cyan]")

        llm_response = self.parse_response(response)
        # console.log(f"[green]Parsed LLM response: {llm_response}[/green]")

        return llm_response

        