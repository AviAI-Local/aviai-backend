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
from fastapi import WebSocket, WebSocketDisconnect
import uuid
import json
import numpy as np
import asyncio
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from agent.history.service import ConversationHistoryService
from agent.history.schema import ConversationHistoryResponse
from agent.config import LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL, TTS_VOICE

console = Console()

class Session:
    """Session that manages its own WebSocket connections and lifecycle"""

    # Will change to store in db after integrate the backend 
    _registry = {}

    def __init__(self, voice: str = "cosette", llm_provider: str = "lmstudio", base_url: str = None, model: str = None):
        self.session_id = str(uuid.uuid4())
        self.voice = voice
        self.buffer = bytearray()
        self.is_speaking = False
        self.session_start_time = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        
        self.service = ConversationHistoryService(history_response=ConversationHistoryResponse(
            conversation_history_id=str(uuid.uuid4()),
            session_id=self.session_id,
            llm_provider=llm_provider,
            model=model,
            content=[],
            timestamp=self.session_start_time.isoformat()
        ))
        self.service.save_conversation_history()

        # Debug: Print LLM provider configuration
        console.print(f"[magenta]============ LLM Configuration ============[/magenta]")
        console.print(f"[magenta]Provider: {llm_provider}[/magenta]")
        console.print(f"[magenta]Base URL: {base_url}[/magenta]")
        console.print(f"[magenta]Model: {model}[/magenta]")
        console.print(f"[magenta]===========================================[/magenta]")

        # Create session-specific LLM service
        prompt = PromptBuilder().build()

        # Conditional LLM initialization based on provider
        if llm_provider == "lmstudio":
            llm = ChatOpenAI(
                base_url=base_url,
                api_key="not-needed",
                model=model
            )
            console.print(f"[green]✓ Using LM Studio with model: {model}[/green]")
        else:  # default to ollama
            llm = ChatOllama(model=model)
            console.print(f"[green]✓ Using Ollama with model: {model}[/green]")

        chain = prompt | llm
        chat = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        self.llm_service = LLMService(chat, session_id=self.session_id)

        # Session-specific TTS with voice setting
        self.tts = TextToSpeechService(voice=voice)

        self.stt = FasterWhisperSTT(
            model_size="small",
            silence_db=-45,
            end_silence_sec=1.2,
        )

        # Register in class registry
        Session._registry[self.session_id] = self

        console.print(f"[green]Session {self.session_id} created with voice={voice}[/green]")

    @classmethod
    def get_by_id(cls, session_id: str) -> Optional["Session"]:
        """Retrieve session by ID from registry"""
        return cls._registry.get(session_id)

    @classmethod
    async def handle_connect(cls, websocket: WebSocket):
        """Handle /session/connect endpoint"""
        await websocket.accept()

        # Wait for initial config
        try:
            msg = await websocket.receive()
            config = json.loads(msg.get("text", "{}"))
            voice = config.get("voice") or TTS_VOICE
            llm_provider = config.get("llm_provider") or LLM_PROVIDER
            llm_provider = LLM_PROVIDER

            base_url = config.get("base_url") or LLM_BASE_URL
            model = config.get("model") or LLM_MODEL
        except:
            voice = "cosette"
            llm_provider = "ollama"
            base_url = None
            model = None

        # Create new session
        session = cls(voice=voice, llm_provider=llm_provider, base_url=base_url, model=model)

        # Send session info to client
        await websocket.send_json({
            "type": "session_created",
            "session_id": session.session_id,
            "voice": session.voice
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

                    if payload.get("type") == "update_voice":
                        session.voice = payload["voice"]
                        session.tts = TextToSpeechService(voice=payload["voice"])
                        await websocket.send_json({
                            "type": "voice_updated",
                            "voice": session.voice
                        })

                except asyncio.TimeoutError:
                    # No message received, send ping to check if client is alive
                    try:
                        await websocket.send_json({"type": "ping"})
                    except:
                        console.print(f"[red]Session {session.session_id} connection lost[/red]")
                        break

        except WebSocketDisconnect:
            console.print(f"[red]Session {session.session_id} disconnected[/red]")
        except Exception as e:
            console.print(f"[red]Error in session connect: {e}[/red]")
        finally:
            session.cleanup()

    async def handle_conversation(self, websocket: WebSocket):
        """Handle /session/conversation endpoint"""
        console.print(f"[green]Conversation started for session {self.session_id}[/green]")

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

                        console.print(f"[yellow]{self.session_id} - You:[/yellow] {text}")

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

                        console.print(f"[cyan]{self.session_id} - Assistant:[/cyan] {content}")

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
            console.print(f"[red]Conversation ended for session {self.session_id}[/red]")
        except Exception as e:
            console.print(f"[red]Error in conversation for session {self.session_id}: {e}[/red]")

    def cleanup(self):
        """Cleanup resources on disconnect"""
        try:
            self.buffer.clear()

            if self.session_id in Session._registry:
                del Session._registry[self.session_id]
                console.print(f"[yellow]Session {self.session_id} cleaned up[/yellow]")
        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")
