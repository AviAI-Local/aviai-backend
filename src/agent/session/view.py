import json
from typing import Dict
from fastapi import APIRouter, Body, Depends, HTTPException, WebSocket
from agent.session.handler import ConversationHandler
from agent.session.schema import SessionResponse, session_example
from agent.session.service import SessionService
from rich.console import Console

from auth.dependencies import get_current_user
from database.config import get_db
from database.model import Account, Session

router = APIRouter()
console = Console()

@router.post("/create")
async def create_session(
    session_data: Dict = Body(...),
    db: Session = Depends(get_db),
    # current_user: Account = Depends(get_current_user)  # TODO: uncomment after testing
):
    service = SessionService(db)
    # session_data["account_id"] = current_user.account_id  # TODO: uncomment after testing
    session = service.create_session(session_data)
    return {"session_id": session.session_id}

@router.get("/")
async def get_session_by_account_id(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user)
):
    service = SessionService(db)
    sessions = service.get_session_by_account(current_user.account_id)
    return sessions

@router.patch(
    "/update",
    response_model=SessionResponse,
    summary="Update any field(s) of a session",
    description="""
Update one or more fields of a session. Only provided fields will be updated. Returns the updated session.

**Fields:**
- `usecase_id`: ID of the usecase (must exist)
- `account_id`: ID of the account (must exist)
- `recording`: Recording URL or path
""",
    responses={
        200: {"content": {"application/json": {"example": session_example}}},
        404: {"description": "Session not found"}
    }
)
async def update_session(
    session_id: str,
    update_data: Dict = Body(..., example={
        "scenario_id": "usecase_002",
        "account_id": "account_002",
        "recording": "https://bucket.s3.amazonaws.com/recordings/session_001_updated.mp3"
    }),
    db: Session = Depends(get_db)
):
    """Update a session and return with histories."""
    service = SessionService(db)
    updated = service.update_session(session_id, update_data)
    # enrich with histories via service helper
    session_full = service.get_session_by_id(session_id)
    if not session_full:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(**session_full)

@router.websocket("/{session_id}/connect")
async def session_connect(session_id: str, websocket: WebSocket, db: Session = Depends(get_db)):
    """Handle session connection - delegates to Session class"""
    await websocket.accept()
    session_service = SessionService(db)
    session = session_service.get_session_by_id(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found in database[/red]")
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close(code=1008, reason="Session not found")
        return
    handler = ConversationHandler(session, db)
    await handler.handle_connect(websocket)
    # await SessionService.handle_connect(websocket)

@router.websocket("/{session_id}/conversation")
async def start_conversation(session_id: str, websocket: WebSocket, db: Session = Depends(get_db)):
    """Handle voice conversation - delegates to Session instance"""
    await websocket.accept()
    handler = None
    try:
        session_service = SessionService(db)
        session = session_service.get_session_by_id(session_id)
        if not session:
            console.print(f"[red]Session {session_id} not found in database[/red]")
            await websocket.send_json({"type": "error", "message": "Session not found"})
            await websocket.close(code=1008, reason="Session not found")
            return

        # Send loading status before heavy initialization
        await websocket.send_json({"type": "status", "state": "loading"})

        handler = ConversationHandler(session, db)
        await handler.handle_conversation(websocket)
    except Exception as e:
        console.print(f"[red]Error in conversation for session {session_id}: {e}[/red]")
    finally:
        # Always cleanup when connection ends (normal or error)
        if handler:
            handler.cleanup()

@router.websocket("/session/disconnect")
async def session_disconnect(websocket: WebSocket, db: Session = Depends(get_db)):
    """Handle explicit disconnect request and cleanup session"""
    try:
        await websocket.accept()

        # Wait for session ID
        try:
            msg = await websocket.receive()
            payload = json.loads(msg.get("text", "{}"))
            session_id = payload.get("session_id")
        except Exception as e:
            console.print(f"[red]Error receiving session_id for disconnect: {e}[/red]")
            await websocket.close(code=1008, reason="No session_id provided")
            return

        # Get session from registry
        # session = SessionService.get_by_id(session_id)
        session_service = SessionService(db)
        session = session_service.get_session_by_id(session_id)
        # await handler.handle_conversation(websocket)
        

        if session:
            # Cleanup the session
            handler = ConversationHandler(session, db)
            # session.cleanup()
            handler.cleanup()
            console.print(f"[green]Session {session_id} explicitly disconnected[/green]")

            # Send confirmation
            await websocket.send_json({
                "type": "disconnect_confirmed",
                "session_id": session_id
            })
        else:
            console.print(f"[yellow]Session {session_id} already cleaned up[/yellow]")

        await websocket.close(code=1000, reason="Session disconnected")
    except Exception as e:
        console.print(f"[red]Error in disconnect endpoint: {e}[/red]")

