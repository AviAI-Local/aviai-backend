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

            # 2. Fix smart quotes and special characters
            content = content.replace('\u201c', '"').replace('\u201d', '"')
            content = content.replace('\u2018', "'").replace('\u2019', "'")
            content = content.replace('\u2026', '...')

            # 3. Find start of JSON object
            start = content.find('{')
            if start == -1:
                raise ValueError("No JSON object found")

            # 4. Parse only the first JSON object, ignoring trailing garbage
            decoder = json.JSONDecoder(strict=False)
            data, _ = decoder.raw_decode(content, start)

            # 5. Validate and return
            if not isinstance(data, dict) or "response" not in data:
                raise ValueError("Invalid JSON structure")

            data.setdefault("avatar_instructions", "neutral")
            data.setdefault("voice_instructions", "neutral")

            return LLMResponse(**data)

        except Exception as e:
            console.log(f"[red]Parse error: {e}[/red]")

            # Fallback: extract fields using regex
            try:
                content = response.content if hasattr(response, "content") else str(response)

                # Extract response field
                resp_match = re.search(r'"response"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
                if resp_match:
                    resp_text = resp_match.group(1)
                    # Clean up escape sequences
                    resp_text = resp_text.replace('\\n', ' ').replace('\\r', ' ')
                    resp_text = re.sub(r'\s+', ' ', resp_text).strip()

                    console.log(f"[green]Fallback extraction successful[/green]")
                    return LLMResponse(
                        response=resp_text,
                        avatar_instructions="neutral",
                        voice_instructions="neutral"
                    )
            except Exception as fallback_error:
                console.log(f"[red]Fallback failed: {fallback_error}[/red]")

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

        content = response.content if hasattr(response, "content") else str(response)
        console.log(f"[cyan]Response content: {content}[/cyan]")

        # Handle empty or invalid responses from LLM
        if not content or content.strip() in ["", "{}", "null", "None"]:
            console.log(f"[red]LLM returned empty/invalid response, using default[/red]")
            return LLMResponse(
                response="I'm sorry, could you please repeat your question?",
                avatar_instructions="default",
                voice_instructions="Speak with a calm, professional tone"
            )

        llm_response = self.parse_response(response)
        return llm_response

        