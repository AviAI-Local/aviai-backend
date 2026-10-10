from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent.prompt.service import PromptService
from agent.prompt.templates import STATIC_PROMPT, OUTPUT_JSON_RULES, SPEECH_NATURALNESS_RULES
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
        placeholders = {
            "{personal_characteristics}": personal_characteristics,
            "{attitude_in_interview}": attitude_in_interview,
            "{rule_interview}": rule_interview,
            "{scenario_text}": scenario_text,
        }

        # A DB-stored template (edited via the prompt admin UI) can have a placeholder
        # token removed by accident. .replace() would then silently drop that scenario
        # data instead of raising, so track and re-append anything that had no token to
        # substitute into — the character must never lose access to its scenario data.
        missing = []
        for token, value in placeholders.items():
            if token in self.system_prompt:
                self.system_prompt = self.system_prompt.replace(token, value)
            elif value:
                missing.append(token)

        if missing:
            console.print(f"[red]⚠ Prompt template is missing placeholder(s) {missing} — appending scenario data so it isn't silently dropped[/red]")
            fallback_block = "\n\n".join(
                f"[{token.strip('{}').replace('_', ' ').title()}]\n{placeholders[token]}"
                for token in missing
            )
            self.system_prompt += f"\n\n{fallback_block}"

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
                ("system", SPEECH_NATURALNESS_RULES),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ]
        )