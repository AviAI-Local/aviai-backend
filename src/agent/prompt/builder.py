from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent.prompt.templates import STATIC_PROMPT, OUTPUT_JSON_RULES

class PromptBuilder:
    """
    Builds a LangChain ChatPromptTemplate for chat with history.
    """

    def __init__(
        self,
        personal_characteristics: str = "",
        attitude_in_interview: str = "",
        rule_interview: str = "",
        scenario_text: str = ""
    ):
        # Fill placeholders in STATIC_PROMPT with scenario data
        self.system_prompt = STATIC_PROMPT.format(
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