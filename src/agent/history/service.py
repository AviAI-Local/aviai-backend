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
    def __init__(self, history_response: ConversationHistoryResponse, db: DBSession):
        self.history_response = history_response
        self.db = db
        self.history_dir = os.path.join(os.path.dirname(__file__), "..", "conversation")
        os.makedirs(self.history_dir, exist_ok=True)

    def create_conversation_history(self) -> bool:
        """Save conversation history to a JSON file"""
        try:
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
            return True
        except Exception as e:
            console.print(f"[red]✗ Failed to create conversation history JSON: {e}[/red]")
            return False 

    def add_conversation_entry(self, user_query: str, response_data: LLMResponse, llm_time: float, tts_time: float) -> bool:
        """Add a conversation entry to the history"""
        try:
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

            success = self.create_conversation_history()
            if success:
                console.print(f"[dim]✓ Conversation entry saved to {self.history_response.session_id}.json[/dim]")
            return success
        except Exception as e:
            console.print(f"[red]✗ Failed to add conversation entry: {e}[/red]")
            return False

    def load_json_file(self) -> ConversationHistoryResponse:
        """Load conversation history from JSON file"""
        file_path = os.path.join(self.history_dir, f"{self.history_response.session_id}.json")
        console.print(f"[dim]Loading JSON from: {file_path}[/dim]")

        if not os.path.exists(file_path):
            console.print(f"[red]✗ File not found: {file_path}[/red]")
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        console.print(f"[dim]✓ JSON loaded, entries count: {len(data.get('content', []))}[/dim]")
        # Pydantic validates structure automatically
        # Raises ValidationError if data doesn't match schema
        return ConversationHistoryResponse(**data)

    def save_conversation_history(self) -> ConversationHistory | None:
        try:
            data = self.load_json_file()
            console.print(f"[dim]Loaded JSON file for session {data.session_id}[/dim]")

            content_as_dicts = [item.model_dump() if hasattr(item, 'model_dump') else item for item in data.content]

            conversation = ConversationHistory(
                conversation_history_id=data.conversation_history_id,
                session_id=data.session_id,
                content=content_as_dicts,
                timestamp=data.timestamp
            )

            self.db.add(conversation)
            self.db.commit()
            # Don't refresh - session might be closed during cleanup

            console.print(f"[green]✓ Conversation history saved to DB successfully (ID: {conversation.conversation_history_id})[/green]")
            return conversation

        except FileNotFoundError as e:
            console.print(f"[red]✗ Failed to save: JSON file not found - {e}[/red]")
            return None
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass  # Session might already be closed
            console.print(f"[red]✗ Failed to save conversation history to DB: {e}[/red]")
            console.print(f"[yellow]Error type: {type(e).__name__}[/yellow]")
            return None

def get_session_history(session_id: str):
    """Get or create in-memory chat history for LangChain (separate from file storage)"""
    if session_id not in _sessions:
        _sessions[session_id] = InMemoryChatMessageHistory()
    return _sessions[session_id]