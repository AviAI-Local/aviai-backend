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

            # 4. Fix smart quotes and special characters
            json_str = json_str.replace('"', '"').replace('"', '"')  # Smart double quotes
            json_str = json_str.replace(''', "'").replace(''', "'")  # Smart single quotes
            json_str = json_str.replace('…', '...')  # Ellipsis

            # 5. Fix control characters - escape them for JSON compatibility
            # First, temporarily protect already-escaped sequences
            json_str = json_str.replace('\\n', '\x00NEWLINE\x00')
            json_str = json_str.replace('\\r', '\x00RETURN\x00')
            json_str = json_str.replace('\\t', '\x00TAB\x00')
            json_str = json_str.replace('\\b', '\x00BACKSPACE\x00')
            json_str = json_str.replace('\\f', '\x00FORMFEED\x00')

            # Now escape actual control characters
            json_str = json_str.replace('\n', '\\n')
            json_str = json_str.replace('\r', '\\r')
            json_str = json_str.replace('\t', '\\t')
            json_str = json_str.replace('\b', '\\b')
            json_str = json_str.replace('\f', '\\f')

            # Remove any other control characters (0x00-0x1F)
            json_str = re.sub(r'[\x01-\x08\x0b\x0e-\x1f]', '', json_str)

            # Restore protected sequences
            json_str = json_str.replace('\x00NEWLINE\x00', '\\n')
            json_str = json_str.replace('\x00RETURN\x00', '\\r')
            json_str = json_str.replace('\x00TAB\x00', '\\t')
            json_str = json_str.replace('\x00BACKSPACE\x00', '\\b')
            json_str = json_str.replace('\x00FORMFEED\x00', '\\f')

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

        