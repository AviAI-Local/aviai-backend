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

