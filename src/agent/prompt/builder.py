from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent.prompt.service import PromptService
from agent.prompt.templates import STATIC_PROMPT, OUTPUT_JSON_RULES
from database.model import Session as DBSession
from rich.console import Console

console = Console()
class PromptBuilder:
    """
    Builds a LangChain ChatPromptTemplate for chat with history.
    """

    def __init__(
        self,
        db: DBSession,  # Add database session
        personal_characteristics: str = "",
        attitude_in_interview: str = "",
        rule_interview: str = "",
        scenario_text: str = "",
        prompt_id: str = ""
    ):
        # Fetch prompts from DB if prompt_id is provided, else use default templates
        if prompt_id:
            prompt_service = PromptService(db)
            prompt_template = prompt_service.get_prompt(prompt_id)

            if prompt_template:
                static_prompt_template = prompt_template.content
                console.print(f"[green]✓ Using prompt from DB: {prompt_template.template_name} (ID: {prompt_id})[/green]")
                console.print(f"[dim]Prompt length: {len(static_prompt_template)} chars[/dim]")
            else:
                # Fallback to default template if prompt not found
                console.print(f"[yellow]⚠ Prompt ID '{prompt_id}' not found, using default STATIC_PROMPT[/yellow]")
                static_prompt_template = STATIC_PROMPT
        else:
            # Use default template if no prompt_id provided
            console.print(f"[dim]No prompt_id provided, using default STATIC_PROMPT[/dim]")
            static_prompt_template = STATIC_PROMPT

        # Fill placeholders using safe string replacement (not .format())
        # This prevents issues when prompt templates contain JSON examples with curly braces
        self.system_prompt = static_prompt_template
        self.system_prompt = self.system_prompt.replace("{personal_characteristics}", personal_characteristics)
        self.system_prompt = self.system_prompt.replace("{attitude_in_interview}", attitude_in_interview)
        self.system_prompt = self.system_prompt.replace("{rule_interview}", rule_interview)
        self.system_prompt = self.system_prompt.replace("{scenario_text}", scenario_text)

        # Escape any remaining curly braces for LangChain template compatibility
        # LangChain interprets {} as template variables, so we need {{ and }} for literal braces
        self.system_prompt = self.system_prompt.replace("{", "{{").replace("}", "}}")

    def build(self) -> ChatPromptTemplate:
        """
        Returns a ChatPromptTemplate equivalent to:

        system -> history -> user input
        """
        return ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                ("system", OUTPUT_JSON_RULES),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ]
        )