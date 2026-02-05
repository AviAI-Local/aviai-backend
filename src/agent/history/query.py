from sqlalchemy.orm import Session
from database.model import ConversationHistory


class ConversationHistoryQueryService:
    """
    Read-only service for fetching conversation history from the database.
    This service is intentionally minimal and side-effect free.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, conversation_history_id: str) -> ConversationHistory | None:
        """
        Fetch a conversation history record by its ID.
        """
        return (
            self.db
            .query(ConversationHistory)
            .filter(
                ConversationHistory.conversation_history_id == conversation_history_id
            )
            .first()
        )

    def get_by_session_id(self, session_id: str) -> list[ConversationHistory]:
        """
        Fetch all conversation histories for a given session ID.
        """
        return (
            self.db
            .query(ConversationHistory)
            .filter(ConversationHistory.session_id == session_id)
            .order_by(ConversationHistory.timestamp.asc())
            .all()
        )
