import time

from agent.prompt.builder import PromptBuilder
from agent.history.service import get_session_history
from agent.llm.service import LLMService
from agent.io.tts.tts_pocket import TextToSpeechService
from agent.io.stt.faster_whisper import FasterWhisperSTT
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
from scenario.service import ScenarioService

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
        # Only include sessions that have conversation history
        result = []
        for session in sessions:
            conv = conv_map.get(session.session_id)
            if not conv:
                continue

            scenario_name = scenario_map.get(session.scenario_id, "Unknown")
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
            recording=None,
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
    
    def update_session(self, session_id: str, update_data: Dict) -> Optional[Dict]:
        """Update session fields and return updated session data."""
        session = self.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Validate usecase exists if usecase_id is being updated
        if "scenario_id" in update_data:
            usecase = self.db.query(Scenario).filter(Scenario.scenario_id == update_data["scenario_id"]).first()
            if not usecase:
                raise HTTPException(status_code=404, detail=f"Scenario with ID {update_data['scenario_id']} does not exist")

        # Validate account exists if account_id is being updated
        if "account_id" in update_data:
            account = self.db.query(Account).filter(Account.account_id == update_data["account_id"]).first()
            if not account:
                raise HTTPException(status_code=404, detail=f"Account with ID {update_data['account_id']} does not exist")

        # Only update fields that exist in the model and are provided
        updatable_fields = ["scenario_id", "account_id", "recording"]
        for field in updatable_fields:
            if field in update_data:
                setattr(session, field, update_data[field])

        self.db.commit()
        self.db.refresh(session)
        return session.to_dict() 



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

def load_scenario_from_api(scenario_id: str, db: DBSession) -> dict:
    service = ScenarioService(db)
    scenario = service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario with ID {scenario_id} not found")
    console.log(f"Loaded scenario from db: {scenario.scenario_name}")
    return scenario.to_dict()