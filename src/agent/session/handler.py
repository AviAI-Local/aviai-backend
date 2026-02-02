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
from agent.config import TTS_VOICE
from agent.history.schema import ConversationHistoryResponse
from agent.history.service import ConversationHistoryService, get_session_history
from agent.io.stt.faster_whisper import FasterWhisperSTT
from agent.io.tts.tts_pocket import TextToSpeechService
from agent.llm.service import LLMService
from agent.prompt.builder import PromptBuilder
from agent.session.service import SessionService, load_usecase_from_api_local
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

        data = load_usecase_from_api_local()

        self.scenario_data = {
            "personal_characteristics": data.get("personal_characteristics", ""),
            "attitude_in_interview": data.get("attitude_in_interview", ""),
            "rule_interview": data.get("rule_interview", ""),
            "scenario_text": data.get("usecase_summary", ""),
            "character_name": data.get("character_name", "")
        }

        # Create session-specific LLM service with scenario data
        prompt = PromptBuilder(
            personal_characteristics=self.scenario_data["personal_characteristics"],
            attitude_in_interview=self.scenario_data["attitude_in_interview"],
            rule_interview=self.scenario_data["rule_interview"],
            scenario_text=self.scenario_data["scenario_text"]
        ).build()

        # Conditional LLM initialization based on provider
        if self.session.llm_provider == "lmstudio":
            llm = ChatOpenAI(
                base_url=os.environ.get("MODEL_URL"),
                api_key=os.environ.get("MODEL_API_KEY"),
                model=os.environ.get("MODEL_NAME")
            )
            # console.print(f"[green]✓ Using LM Studio with model: {model}[/green]")
        else:  # default to ollama
            model = os.environ.get("OLLAMA_MODEL_NAME")
            llm = ChatOllama(model=model)
            # console.print(f"[green]✓ Using Ollama with model: {model}[/green]")
        
        chain = prompt | llm
        chat = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        self.llm_service = LLMService(chat, session_id=self.session.session_id)

        # Session-specific TTS with voice setting
        self.tts = TextToSpeechService(voice=TTS_VOICE)

        self.stt = FasterWhisperSTT(
            model_size="small",
            silence_db=-45,
            end_silence_sec=1.2,
        )

    async def handle_connect(self, websocket: WebSocket):
        """Handle /session/connect endpoint"""
        await websocket.accept()

        # # Wait for initial config
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

        # Create new session
        # session = cls(
        #     session_id=str(uuid.uuid4()), 
        #     scenario_id=str(uuid.uuid4()), 
        #     voice=voice, 
        #     llm_provider=llm_provider, 
        #     base_url=base_url, 
        #     model=model
        # )


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

    async def handle_conversation(self, websocket: WebSocket):
        """Handle /session/conversation endpoint"""
        console.print(f"[green]Conversation started for session {self.session.session_id}[/green]")

        await websocket.send_json({
            "type": "status",
            "state": "listening"
        })

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

                    if payload["type"] == "end_of_utterance":
                        if not self.buffer:
                            continue

                        # Transcribe
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

                        console.print(f"[yellow]{self.session.session_id} - You:[/yellow] {text}")

                        start = time.perf_counter()
                        # Generate response
                        response = await asyncio.to_thread(
                            self.llm_service.get_response,
                            text
                        )
                        llm_time = time.perf_counter() - start

                        content = response.response
                        await websocket.send_json({
                            "type": "assistant_text",
                            "content": content
                        })

                        console.print(f"[cyan]{self.session.session_id} - Assistant:[/cyan] {content}")

                        start = time.perf_counter()
                        # Generate TTS
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

                        # Save conversation entry to history file with timing
                        self.service.add_conversation_entry(
                            user_query=text,
                            response_data=response,
                            # user_emotion="neutral",
                            llm_time=llm_time,
                            tts_time=tts_time
                        )

                        self.is_speaking = True
                        await websocket.send_bytes(pcm_bytes)
                        await websocket.send_json({
                            "type": "status",
                            "state": "speaking"
                        })
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
