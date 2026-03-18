from pydantic import BaseModel
from typing import Optional
from agent.history.schema import ConversationHistoryResponse, conversation_history_example

class SessionResponse(BaseModel):
    session_id: str
    scenario_name: str
    scenario_id: str
    account_id: str
    created_at: str
    recording: Optional[str] = None
    conversation_history: Optional[ConversationHistoryResponse] = None

session_example = {
    "session_id": "session_001",
    "usecase_id": "usecase_001",
    "account_id": "account_001",
    "created_at": "2024-06-07T12:30:45+07:00",
    "recording": "https://bucket.s3.amazonaws.com/recordings/session_001.mp3",
    "conversation_history": [conversation_history_example]
}