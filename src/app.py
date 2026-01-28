from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console
import json

from agent.session.service import SessionService

console = Console()

app = FastAPI(title="Realtime Voice Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================
# WebSocket Endpoints
# ======================

@app.websocket("/session/connect")
async def session_connect(websocket: WebSocket):
    """Handle session connection - delegates to Session class"""
    await SessionService.handle_connect(websocket)

@app.websocket("/session/conversation")
async def start_conversation(websocket: WebSocket):
    """Handle voice conversation - delegates to Session instance"""
    await websocket.accept()

    # Wait for session ID
    try:
        msg = await websocket.receive()
        payload = json.loads(msg.get("text", "{}"))
        session_id = payload.get("session_id")
    except:
        await websocket.close(code=1008, reason="No session_id provided")
        return

    # Get session from registry
    session = SessionService.get_by_id(session_id)
    if not session:
        await websocket.close(code=1008, reason="Invalid session_id")
        return

    # Delegate to session's conversation handler
    await session.handle_conversation(websocket)

@app.websocket("/session/disconnect")
async def session_disconnect(websocket: WebSocket):
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
        session = SessionService.get_by_id(session_id)
        if session:
            # Cleanup the session
            session.cleanup()
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

