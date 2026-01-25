from datetime import datetime
import json
import os
from typing import List
from zoneinfo import ZoneInfo
from langchain_core.chat_history import InMemoryChatMessageHistory
from agent.history.schema import ConversationHistoryResponse, ConversationHistoryContent
from agent.llm.schema import LLMResponse
from rich.console import Console
from database.model import ConversationHistory, Session as DBSession, Scenario

_sessions = {}
console = Console()


class ConversationHistoryService:
    def __init__(self, history_response: ConversationHistoryResponse):
        self.history_response = history_response
        # self.db = db
        self.history_dir = os.path.join(os.path.dirname(__file__), "..", "conversation")
        os.makedirs(self.history_dir, exist_ok=True)

    def create_conversation_history(self):
        """Save conversation history to a JSON file"""
        history_data = {
            "conversation_history_id": self.history_response.conversation_history_id,
            "session_id": self.history_response.session_id,
            "llm_provider": self.history_response.llm_provider,
            "model": self.history_response.model,
            "content": self.history_response.content,
            "timestamp": self.history_response.timestamp
        }

        file_path = os.path.join(self.history_dir, f"{self.history_response.session_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4, ensure_ascii=False) 

    def add_conversation_entry(self, user_query: str, response_data: LLMResponse, llm_time: float, tts_time: float):
        """Add a conversation entry to the history"""
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

        entry = ConversationHistoryContent(
            timestamp=now.timestamp(),
            datetime=now.isoformat(),
            user_query=user_query,
            response=response_data.response,
            user_emotion="default",
            voice_instructions=response_data.voice_instructions,
            avatar_instructions=response_data.avatar_instructions,
            llm_time=round(llm_time, 2),
            tts_time=round(tts_time, 2)
        )

        # Append to history_response.content (the source of truth)
        self.history_response.content.append(entry.model_dump())

        self.create_conversation_history()
        console.print(f"[dim]Conversation entry saved to {self.history_response.session_id}.json[/dim]")


def get_session_history(session_id: str):
    """Get or create in-memory chat history for LangChain (separate from file storage)"""
    if session_id not in _sessions:
        _sessions[session_id] = InMemoryChatMessageHistory()
    return _sessions[session_id]