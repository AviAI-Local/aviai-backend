import asyncio
from datetime import datetime
import json
import os
import time
import uuid
from zoneinfo import ZoneInfo
from fastapi import WebSocket, WebSocketDisconnect
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
import numpy as np
from rich.console import Console
from agent.history.schema import ConversationHistoryResponse
from agent.history.service import ConversationHistoryService, get_session_history
from agent.models import get_tts, get_stt
from agent.llm.service import LLMService
from agent.prompt.builder import PromptBuilder
from agent.session.service import SessionService, load_usecase_from_api_local, load_scenario_from_api
from database.model import Session as DBSession
from langchain_core.runnables.history import RunnableWithMessageHistory

console = Console()

class ConversationHandler:
    def __init__(self, session: DBSession, db: DBSession):
        self.session = session
        self.session_start_time = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        self.is_speaking = False
        self.buffer = bytearray()
        self.db = db

        # Debug: Print LLM provider configuration
        console.print(f"[magenta]============ LLM Configuration ============[/magenta]")
        console.print(f"[magenta]Provider: {self.session.llm_provider}[/magenta]")
        console.print(f"[magenta]Model: {self.session.model}[/magenta]")
        console.print(f"[magenta]===========================================[/magenta]")
        
        self.service = ConversationHistoryService(history_response=ConversationHistoryResponse(
            conversation_history_id=str(uuid.uuid4()),
            session_id=self.session.session_id,
            llm_provider=self.session.llm_provider,
            model=self.session.model,
            content=[],
            timestamp=self.session_start_time.isoformat()
        ), db=self.db)
        self.service.create_conversation_history()

        # data = load_usecase_from_api_local()
        data = load_scenario_from_api(self.session.scenario_id, self.db)

        self.scenario_data = {
            "personal_characteristics": data.get("personal_characteristics", ""),
            "attitude_in_interview": data.get("attitude_in_interview", ""),
            "rule_interview": data.get("rule_interview", ""),
            "scenario_text": data.get("usecase_summary", ""),
            "character_name": data.get("character_name", ""),
            "prompt_id": data.get("prompt_id", "")
        }

        # Create session-specific LLM service with scenario data
        prompt = PromptBuilder(
            db=self.db,
            personal_characteristics=self.scenario_data["personal_characteristics"],
            attitude_in_interview=self.scenario_data["attitude_in_interview"],
            rule_interview=self.scenario_data["rule_interview"],
            scenario_text=self.scenario_data["scenario_text"],
            prompt_id=self.scenario_data["prompt_id"]
        ).build()

        # Conditional LLM initialization based on provider
        if self.session.llm_provider == "lmstudio":
            llm = ChatOpenAI(
                base_url=os.environ.get("MODEL_URL"),
                api_key=os.environ.get("MODEL_API_KEY"),
                model=os.environ.get("MODEL_NAME"),
            )
            # console.print(f"[green]✓ Using LM Studio with model: {model}[/green]")
        else:  # default to ollama
            model = os.environ.get("OLLAMA_MODEL_NAME", "gemma3")
            base_url = os.environ.get("OLLAMA_MODEL_URL", "http://localhost:11434")
            llm = ChatOllama(model=model, base_url=base_url, format="json")
            console.print(f"[green]Using Ollama model: {model}[/green]")
            # console.print(f"[green]✓ Using Ollama with model: {model}[/green]")
        
        chain = prompt | llm
        chat = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        self.llm_service = LLMService(chat, session_id=self.session.session_id)

        # Use shared TTS and STT instances (pre-loaded at startup)
        self.tts = get_tts()
        self.stt = get_stt()

    async def handle_connect(self, websocket: WebSocket):
        """Handle /session/connect endpoint"""
        # Note: websocket.accept() is called in view.py before this method

        # Send session info to client
        await websocket.send_json({
            "type": "session_created",
            "session_id": self.session.session_id,
        })

        # Keep connection alive for session management
        try:
            while True:
                try:
                    # Timeout: if no message in 30s, check if client is alive
                    msg = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=30.0
                    )
                    payload = json.loads(msg.get("text", "{}"))

                    # Handle ping from client
                    if payload.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                        continue

                except asyncio.TimeoutError:
                    # No message received, send ping to check if client is alive
                    try:
                        await websocket.send_json({"type": "ping"})
                    except:
                        console.print(f"[red]Session {self.session.session_id} connection lost[/red]")
                        break

        except WebSocketDisconnect:
            console.print(f"[red]Session {self.session.session_id} disconnected[/red]")
        except Exception as e:
            console.print(f"[red]Error in session connect: {e}[/red]")
        finally:
            self.cleanup()

    async def process_response(self, websocket: WebSocket, text: str):
        """Process user text through LLM and TTS, send response back"""
        console.print(f"[yellow]{self.session.session_id} - You:[/yellow] {text}")

        try:
            await websocket.send_json({
                "type": "user_query",
                "query": text
            })
        except WebSocketDisconnect:
            console.print(f"[red]Client disconnected during process_response for session {self.session.session_id}[/red]")
            raise

        start = time.perf_counter()
        response = await asyncio.to_thread(
            self.llm_service.get_response,
            text
        )
        llm_time = time.perf_counter() - start

        content = response.response
        try:
            await websocket.send_json({
                "type": "assistant_text",
                "content": content,
                "voice_instructions": response.voice_instructions,
                "avatar_instructions": response.avatar_instructions
            })
        except WebSocketDisconnect:
            console.print(f"[red]Client disconnected while sending response for session {self.session.session_id}[/red]")
            raise

        console.print(f"[cyan]{self.session.session_id} - Assistant:[/cyan] {content}")

        start = time.perf_counter()
        sr, audio_out = await asyncio.to_thread(
            self.tts.long_form_synthesize,
            content,
            None,
            0.5,
            0.5
        )
        tts_time = time.perf_counter() - start

        pcm_bytes = (audio_out * 32767).astype(np.int16).tobytes()
        console.print(f"[dim]LLM time: {llm_time:.2f}s | TTS time: {tts_time:.2f}s[/dim]")

        self.service.add_conversation_entry(
            user_query=text,
            response_data=response,
            llm_time=llm_time,
            tts_time=tts_time
        )

        self.is_speaking = True
        try:
            await websocket.send_bytes(pcm_bytes)
            await websocket.send_json({
                "type": "status",
                "state": "speaking"
            })
        except WebSocketDisconnect:
            console.print(f"[red]Client disconnected while sending audio for session {self.session.session_id}[/red]")
            raise

    async def handle_conversation(self, websocket: WebSocket):
        """Handle /session/conversation endpoint - supports both voice and text input"""
        console.print(f"[green]Conversation started for session {self.session.session_id}[/green]")

        try:
            await websocket.send_json({
                "type": "status",
                "state": "listening"
            })
        except WebSocketDisconnect:
            console.print(f"[red]Client disconnected before conversation started for session {self.session.session_id}[/red]")
            return
        except Exception as e:
            console.print(f"[red]Failed to send initial status for session {self.session.session_id}: {e}[/red]")
            return

        try:
            while True:
                msg = await websocket.receive()

                # Handle JSON messages
                if "text" in msg and msg["text"]:
                    payload = json.loads(msg["text"])

                    if payload["type"] == "audio_playback_complete":
                        self.is_speaking = False
                        await websocket.send_json({
                            "type": "status",
                            "state": "listening"
                        })
                        continue

                    # Handle text input directly (skip STT)
                    if payload["type"] == "text_message":
                        text = payload.get("text", "").strip()
                        if not text:
                            continue
                        await self.process_response(websocket, text)
                        continue

                    # Handle voice input (STT → LLM → TTS)
                    if payload["type"] == "end_of_utterance":
                        if not self.buffer:
                            continue

                        audio_np = (
                            np.frombuffer(self.buffer, dtype=np.int16)
                            .astype(np.float32) / 32768.0
                        )
                        self.buffer.clear()

                        text = await asyncio.to_thread(
                            self.stt.transcribe,
                            audio_np
                        )

                        if not text:
                            continue

                        await self.process_response(websocket, text)
                        continue

                # Handle binary audio data
                if self.is_speaking:
                    continue

                data = msg.get("bytes")
                if data:
                    self.buffer.extend(data)

        except WebSocketDisconnect:
            console.print(f"[red]Conversation ended for session {self.session.session_id}[/red]")
        except Exception as e:
            console.print(f"[red]Error in conversation for session {self.session.session_id}: {e}[/red]")

    def cleanup(self):
        """Cleanup resources on disconnect"""
        from database.config import SessionLocal

        try:
            self.buffer.clear()
            console.print(f"[dim]Cleaning up session: {self.session.session_id}[/dim]")

            # Create a fresh DB session for cleanup (original might be closed)
            db = SessionLocal()
            try:
                self.service.db = db  # Update the service's db reference
                self.service.save_conversation_history()
                db.commit()
            finally:
                db.close()

            console.print(f"[yellow]Session {self.session.session_id} cleaned up[/yellow]")

        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")
