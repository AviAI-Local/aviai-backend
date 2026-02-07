from typing import List, Optional
from pydantic import BaseModel


class ConversationHistoryContent(BaseModel):
    timestamp: float
    datetime: str
    user_query: str
    response: str
    user_emotion: str
    voice_instructions: str
    avatar_instructions: str
    llm_time: float
    tts_time: float

class ConversationHistoryResponse(BaseModel):
    conversation_history_id: str
    session_id: str
    llm_provider: str
    model: str
    content: List[ConversationHistoryContent]
    timestamp: Optional[str] = None

conversation_history_example = {
    "conversation_history_id": "c1234567-89ab-4cde-f012-3456789abcde",
    "session_id": "abc12345-6789-4def-0123-456789abcdef",
    "content": [
        {
            "timestamp": 1749998218.4276192,
            "datetime": "2025-06-15T21:36:58.427619+07:00",
            "user_query": "Can you please introduce yourself?",
            "response": "I'm Linh, a flight engineer from Hanoi, currently working at VAECO in Ho Chi Minh City.",
            "user_emotion": "neutral",
            "voice_instructions": "Speak with a calm, professional tone, clear and measured pace.",
            "avatar_instructions": "neutral"
        }
    ],
    "timestamp": "2025-06-15T21:36:58.427619+07:00"
}