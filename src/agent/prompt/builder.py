from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent.prompt.templates import AGENT_INSTRUCTIONS, STATIC_PROMPT, OUTPUT_JSON_RULES

class PromptBuilder:
    """
    Builds a LangChain ChatPromptTemplate for chat with history.
    """

    def __init__(self, system_prompt: str | None = None):
        self.system_prompt = STATIC_PROMPT
        self.agent_instructions = AGENT_INSTRUCTIONS
        # self.output_rules = OUTPUT_JSON_RULES

    def build(self) -> ChatPromptTemplate:
        """
        Returns a ChatPromptTemplate equivalent to:

        system -> history -> user input
        """
        return ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                # ("system", self.agent_instructions),
                ("system", OUTPUT_JSON_RULES),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ]
        )