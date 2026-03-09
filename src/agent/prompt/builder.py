from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent.prompt.service import PromptService
from agent.prompt.templates import STATIC_PROMPT, OUTPUT_JSON_RULES
from database.model import Session as DBSession

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
            else:
                # Fallback to default template if prompt not found
                static_prompt_template = STATIC_PROMPT
        else:
            # Use default template if no prompt_id provided
            static_prompt_template = STATIC_PROMPT

        # Fill placeholders
        self.system_prompt = static_prompt_template.format(
            personal_characteristics=personal_characteristics,
            attitude_in_interview=attitude_in_interview,
            rule_interview=rule_interview,
            scenario_text=scenario_text
        )

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