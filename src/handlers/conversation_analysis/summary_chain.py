from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from .model import LLMConversationSummary


SYSTEM_PROMPT = """
You are an expert conversation analyst specializing in emotion analysis and conversation summarization. Your task is to provide a comprehensive summary of the user's emotional journey throughout the conversation.

Guidelines for conversation summary:
- Analyze the overall emotional pattern and tone of the user
- Identify key emotional changes and transitions
- Highlight specific moments where emotions shifted
- Provide insights into the user's emotional state and behavior
- Write in a professional, analytical tone
- Be specific about emotional changes and their context
- Focus on the user's emotional expression, not the content of responses

Example summary format:
"The user showed overall calmness and politeness throughout the interview. However, the tone changed to more serious and inquisitive when they asked about the incident details. There was a noticeable shift from neutral to concerned when discussing safety procedures, indicating genuine worry about the situation."

You MUST return valid JSON in this EXACT structure:

{{
  "conversation_summary": "string"
}}

Return ONLY the conversation summary in the specified JSON format.
"""


parser = PydanticOutputParser(
    pydantic_object=LLMConversationSummary
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("user", "Analyze this conversation history for emotional summary: {conversation_data}")
    ]
).partial(format_instructions=parser.get_format_instructions())

llm = ChatOllama(
    base_url="http://localhost:11434",
    model="gemma3",
    temperature=0.3,
    format="json"
)

conversation_summary_chain = prompt | llm | parser
