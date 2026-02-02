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

            # 2. Remove markdown code fences
            content = re.sub(r"```json\s*", "", content)
            content = re.sub(r"```\s*", "", content)
            content = content.strip()

            # 3. Find JSON object boundaries
            start = content.find('{')
            end = content.rfind('}')
            if start == -1 or end == -1:
                raise ValueError("No JSON object found")

            json_str = content[start:end+1]

            # 4. Fix newlines inside string values by escaping them properly
            # Replace actual newlines with escaped \n for JSON compatibility
            def fix_string_newlines(match):
                s = match.group(0)
                # Replace actual newlines with \n escape sequence
                s = s.replace('\n', '\\n')
                s = s.replace('\r', '\\r')
                return s

            # Match string values and fix newlines inside them
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)

            # 5. Parse JSON
            data = json.loads(json_str)

            # 6. Validate and return
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

        # console.log(f"[cyan]Raw LLM response: {response}[/cyan]")

        # if hasattr(response, "content"):
        console.log(f"[cyan]Response content: {response.content}[/cyan]")

        llm_response = self.parse_response(response)
        # console.log(f"[green]Parsed LLM response: {llm_response}[/green]")

        return llm_response

        