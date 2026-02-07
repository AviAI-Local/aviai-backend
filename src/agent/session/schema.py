from pydantic import BaseModel
from typing import Optional
from agent.history.schema import ConversationHistoryResponse

class SessionResponse(BaseModel):
    session_id: str
    scenario_name: str
    account_id: str
    created_at: str
    recording: Optional[str] = None
    conversation_history: Optional[ConversationHistoryResponse] = None