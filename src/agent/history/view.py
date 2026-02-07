from typing import List
from fastapi import APIRouter, Depends, HTTPException
from rich.console import Console

from agent.history.schema import ConversationHistoryResponse, conversation_history_example
from agent.history.service import ConversationHistoryService
from auth.dependencies import get_current_user
from database.config import get_db
from database.model import Account, Session
from handlers.conversation_analysis.view import convert_to_vietnam_time

router = APIRouter()

console = Console()

@router.get("/", response_model=List[ConversationHistoryResponse])
async def get_conversation_by_account(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user)
):
    """Get all conversation histories for the current authenticated user."""
    service = ConversationHistoryService(db)
    conversations = service.get_conversation_histories_by_account(current_user.account_id)
    return conversations

@router.get(
    "/{conversation_id}",
    response_model=ConversationHistoryResponse,
    responses={200: {"content": {"application/json": {"examples": {"default": {"value": conversation_history_example}}}}}}
)
async def get_conversation_by_id(conversation_id: str, db: Session = Depends(get_db)):
    """Get a specific conversation history by ID."""
    service = ConversationHistoryService(db)
    conversation = service.get_conversation_history(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation history not found")
    return ConversationHistoryResponse(
        conversation_history_id=conversation.conversation_history_id,
        session_id=conversation.session_id,
        content=conversation.content,
        timestamp=convert_to_vietnam_time(conversation.timestamp).isoformat() if conversation.timestamp else None
    )

@router.get(
    "/session/{session_id}",
    response_model=ConversationHistoryResponse,
    responses={200: {"content": {"application/json": {"examples": {"default": {"value": conversation_history_example}}}}}}
)
async def get_conversation_session_id(session_id: str, db: Session = Depends(get_db)):
    """Get all conversation histories for a specific session."""
    service = ConversationHistoryService(db)
    try:
        conversations = service.get_conversation_histories_by_session(session_id)
        return [ConversationHistoryResponse(
            conversation_history_id=conv.conversation_history_id,
            session_id=conv.session_id,
            content=conv.content,
            timestamp=convert_to_vietnam_time(conv.timestamp).isoformat() if conv.timestamp else None
        ) for conv in conversations]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

  