import time
from agent.prompt.builder import PromptBuilder
from agent.history.service import get_session_history
from agent.llm.service import LLMService
from agent.io.tts.tts_pocket import TextToSpeechService
from agent.io.stt.faster_whisper import FasterWhisperSTT
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from rich.console import Console
from fastapi import HTTPException, WebSocket, WebSocketDisconnect, Depends
import uuid
import json
import numpy as np
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from agent.session.schema import SessionResponse
from database.model import Account, ConversationHistory, Scenario, Session as DBSession, get_vietnam_time
from agent.history.service import ConversationHistoryService
from agent.history.schema import ConversationHistoryResponse
from agent.config import LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL, TTS_VOICE
from database.config import SessionLocal

console = Console()

class SessionService:
    """Session that manages its own WebSocket connections and lifecycle"""
    def __init__(self, db: DBSession):
        self.db = db
        self.buffer = bytearray()

    def get_session_by_account(self, account_id: str) -> List[SessionResponse]:
        """Get all sessions for a specific account."""
        # Verify account exists
        account = self.db.query(Account).filter(Account.account_id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Account with ID {account_id} does not exist")

        # Get all sessions belonging to this account
        sessions = self.db.query(DBSession).filter(DBSession.account_id == account_id).all()

        # Return empty list if no sessions found
        if not sessions:
            return []

        # Get scenario names by scenario_id
        scenario_ids = list(set(s.scenario_id for s in sessions))
        scenarios = self.db.query(Scenario).filter(Scenario.scenario_id.in_(scenario_ids)).all()
        scenario_map = {s.scenario_id: s.scenario_name for s in scenarios}

        # Get conversation histories for all sessions
        session_ids = [s.session_id for s in sessions]
        conversations = self.db.query(ConversationHistory).filter(
            ConversationHistory.session_id.in_(session_ids)
        ).all()
        # Map session_id -> conversation history
        conv_map = {c.session_id: c for c in conversations}

        # Build response with scenario_name and conversation_history
        result = []
        for session in sessions:
            scenario_name = scenario_map.get(session.scenario_id, "Unknown")
            conv = conv_map.get(session.session_id)

            # Build conversation history response if exists
            conv_response = None
            if conv:
                conv_response = ConversationHistoryResponse(
                    conversation_history_id=conv.conversation_history_id,
                    session_id=conv.session_id,
                    llm_provider=session.llm_provider,
                    model=session.model,
                    content=conv.content,
                    timestamp=conv.timestamp.isoformat() if conv.timestamp else None
                )

            result.append(SessionResponse(
                session_id=session.session_id,
                scenario_id=session.scenario_id,
                scenario_name=scenario_name,
                account_id=session.account_id,
                created_at=session.created_at.isoformat() if session.created_at else None,
                recording=session.recording,
                conversation_history=conv_response
            ))
        return result

    def create_session(self, session_data: Dict) -> DBSession:
        self.validate_session_data(session_data)

        session = DBSession(
            session_id=str(uuid.uuid4()),
            scenario_id=session_data["scenario_id"],
            account_id=session_data["account_id"],
            created_at=get_vietnam_time(),
            recording="123",
            llm_provider=LLM_PROVIDER,
            model=LLM_MODEL,
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def validate_session_data(self, session_data: Dict):
        """Validate session data and raise appropriate exceptions."""
        # Validate required fields
        required_fields = ["scenario_id", "account_id"]
        for field in required_fields:
            if field not in session_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        # Validate usecase exists
        scenario = self.db.query(Scenario).filter(Scenario.scenario_id == session_data["scenario_id"]).first()
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario with ID {session_data['scenario_id']} does not exist")

        # Validate account exists
        account = self.db.query(Account).filter(Account.account_id == session_data["account_id"]).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Account with ID {session_data['account_id']} does not exist")
        
    def get_session_by_id(self, session_id: str) -> Optional[DBSession]:
        return self.db.query(DBSession).filter(DBSession.session_id == session_id).first()

    # @classmethod
    # async def handle_connect(self, websocket: WebSocket):
    #     """Handle /session/connect endpoint"""
    #     await websocket.accept()

        # Wait for initial config
        # try:
        #     msg = await websocket.receive()
        #     config = json.loads(msg.get("text", "{}"))
        #     voice = config.get("voice") or TTS_VOICE
        #     llm_provider = config.get("llm_provider") or LLM_PROVIDER
        #     llm_provider = LLM_PROVIDER

        #     base_url = config.get("base_url") or LLM_BASE_URL
        #     model = config.get("model") or LLM_MODEL
        # except:
        #     voice = "cosette"
        #     llm_provider = "ollama"
        #     base_url = None
        #     model = None

    #     # Create new session
    #     # session = cls(
    #     #     session_id=str(uuid.uuid4()), 
    #     #     scenario_id=str(uuid.uuid4()), 
    #     #     voice=voice, 
    #     #     llm_provider=llm_provider, 
    #     #     base_url=base_url, 
    #     #     model=model
    #     # )


    #     # Send session info to client
    #     await websocket.send_json({
    #         "type": "session_created",
    #         "session_id": self.session_id,
    #         "voice": self.voice
    #     })

    #     # Keep connection alive for session management
    #     try:
    #         while True:
    #             try:
    #                 # Timeout: if no message in 30s, check if client is alive
    #                 msg = await asyncio.wait_for(
    #                     websocket.receive(),
    #                     timeout=30.0
    #                 )
    #                 payload = json.loads(msg.get("text", "{}"))

    #                 # Handle ping from client
    #                 if payload.get("type") == "ping":
    #                     await websocket.send_json({"type": "pong"})
    #                     continue

    #                 if payload.get("type") == "update_voice":
    #                     self.voice = payload["voice"]
    #                     self.tts = TextToSpeechService(voice=payload["voice"])
    #                     await websocket.send_json({
    #                         "type": "voice_updated",
    #                         "voice": self.voice
    #                     })

    #             except asyncio.TimeoutError:
    #                 # No message received, send ping to check if client is alive
    #                 try:
    #                     await websocket.send_json({"type": "ping"})
    #                 except:
    #                     console.print(f"[red]Session {self.session_id} connection lost[/red]")
    #                     break

    #     except WebSocketDisconnect:
    #         console.print(f"[red]Session {self.session_id} disconnected[/red]")
    #     except Exception as e:
    #         console.print(f"[red]Error in session connect: {e}[/red]")
    #     finally:
    #         self.cleanup()

    # async def handle_conversation(self, websocket: WebSocket):
    #     """Handle /session/conversation endpoint"""
    #     console.print(f"[green]Conversation started for session {self.session_id}[/green]")

    #     await websocket.send_json({
    #         "type": "status",
    #         "state": "listening"
    #     })

    #     try:
    #         while True:
    #             msg = await websocket.receive()

    #             # Handle JSON messages
    #             if "text" in msg and msg["text"]:
    #                 payload = json.loads(msg["text"])

    #                 if payload["type"] == "audio_playback_complete":
    #                     self.is_speaking = False
    #                     await websocket.send_json({
    #                         "type": "status",
    #                         "state": "listening"
    #                     })
    #                     continue

    #                 if payload["type"] == "end_of_utterance":
    #                     if not self.buffer:
    #                         continue

    #                     # Transcribe
    #                     audio_np = (
    #                         np.frombuffer(self.buffer, dtype=np.int16)
    #                         .astype(np.float32) / 32768.0
    #                     )
    #                     self.buffer.clear()

    #                     text = await asyncio.to_thread(
    #                         self.stt.transcribe,
    #                         audio_np
    #                     )

    #                     if not text:
    #                         continue

    #                     console.print(f"[yellow]{self.session_id} - You:[/yellow] {text}")

    #                     start = time.perf_counter()
    #                     # Generate response
    #                     response = await asyncio.to_thread(
    #                         self.llm_service.get_response,
    #                         text
    #                     )
    #                     llm_time = time.perf_counter() - start

    #                     content = response.response
    #                     await websocket.send_json({
    #                         "type": "assistant_text",
    #                         "content": content
    #                     })

    #                     console.print(f"[cyan]{self.session_id} - Assistant:[/cyan] {content}")

    #                     start = time.perf_counter()
    #                     # Generate TTS
    #                     sr, audio_out = await asyncio.to_thread(
    #                         self.tts.long_form_synthesize,
    #                         content,
    #                         None,
    #                         0.5,
    #                         0.5
    #                     )
    #                     tts_time = time.perf_counter() - start

    #                     pcm_bytes = (audio_out * 32767).astype(np.int16).tobytes()
    #                     console.print(f"[dim]LLM time: {llm_time:.2f}s | TTS time: {tts_time:.2f}s[/dim]")

    #                     # Save conversation entry to history file with timing
    #                     self.service.add_conversation_entry(
    #                         user_query=text,
    #                         response_data=response,
    #                         # user_emotion="neutral",
    #                         llm_time=llm_time,
    #                         tts_time=tts_time
    #                     )

    #                     self.is_speaking = True
    #                     await websocket.send_bytes(pcm_bytes)
    #                     await websocket.send_json({
    #                         "type": "status",
    #                         "state": "speaking"
    #                     })
    #                     continue

    #             # Handle binary audio data
    #             if self.is_speaking:
    #                 continue

    #             data = msg.get("bytes")
    #             if data:
    #                 self.buffer.extend(data)

    #     except WebSocketDisconnect:
    #         console.print(f"[red]Conversation ended for session {self.session_id}[/red]")
    #     except Exception as e:
    #         console.print(f"[red]Error in conversation for session {self.session_id}: {e}[/red]")

    # def cleanup(self):
    #     """Cleanup resources on disconnect"""
    #     try:
    #         self.buffer.clear()

    #         if self.session_id in SessionService._registry:
    #             del SessionService._registry[self.session_id]
    #             self.service.save_conversation_history()
    #             self.db.close()
    #             console.print(f"[yellow]Session {self.session_id} cleaned up[/yellow]")
                
    #     except Exception as e:
    #         console.print(f"[red]Error during cleanup: {e}[/red]")


def load_usecase_from_api_local() -> dict:
    """
    For local testing: load usecase data from scenario/usecase_1.json.        
    Returns:
        dict: Usecase data from the local file.
    """
    import os
    # Get project root (go up from src/agent/session/service.py to project root)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    local_path = os.path.join(project_root, "scenario", "usecase_1.json")
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            usecase_data = json.load(f)
        console.log(f"Loaded usecase from local file: {usecase_data.get('usecase_name', 'Unknown')}")
        return usecase_data
    except Exception as e:
        console.log(f"Error loading usecase from local file: {e}")
        raise