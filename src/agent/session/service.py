from agent.prompt.builder import PromptBuilder
from agent.memory.history import get_session_history
from agent.llm.service import LLMService
from agent.io.tts.tts_pocket import TextToSpeechService
from agent.io.stt.faster_whisper import FasterWhisperSTT
from langchain_ollama import ChatOllama
from langchain_core.runnables.history import RunnableWithMessageHistory
from rich.console import Console
from fastapi import WebSocket, WebSocketDisconnect
import uuid
import json
import numpy as np
import asyncio
from typing import Optional
from agent.io.stt.faster_whisper import FasterWhisperSTT


console = Console()

class Session:
    """Session that manages its own WebSocket connections and lifecycle"""

    # Will change to store in db after integrate the backend 
    _registry = {}

    def __init__(self, voice: str = "cosette"):
        self.session_id = str(uuid.uuid4())
        self.voice = voice
        self.buffer = bytearray()
        self.is_speaking = False

        # Create session-specific LLM service
        prompt = PromptBuilder().build()
        llm = ChatOllama(model="gemma3")
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
            voice = config.get("voice", "cosette")
        except:
            voice = "cosette"

        # Create new session
        session = cls(voice=voice)

        # Send session info to client
        await websocket.send_json({
            "type": "session_created",
            "session_id": session.session_id,
            "voice": session.voice
        })

        # Keep connection alive for session management
        try:
            while True:
                msg = await websocket.receive()
                payload = json.loads(msg.get("text", "{}"))

                if payload["type"] == "update_voice":
                    session.voice = payload["voice"]
                    session.tts = TextToSpeechService(voice=payload["voice"])
                    await websocket.send_json({
                        "type": "voice_updated",
                        "voice": session.voice
                    })

        except WebSocketDisconnect:
            session.cleanup()
            console.print(f"[red]Session {session.session_id} disconnected[/red]")
        except Exception as e:
            console.print(f"[red]Error in session connect: {e}[/red]")
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

                        # Generate response
                        response = await asyncio.to_thread(
                            self.llm_service.get_response,
                            text
                        )

                        content = response.response
                        await websocket.send_json({
                            "type": "assistant_text",
                            "content": content
                        })

                        console.print(f"[cyan]{self.session_id} - Assistant:[/cyan] {content}")

                        # Generate TTS
                        sr, audio_out = await asyncio.to_thread(
                            self.tts.long_form_synthesize,
                            content,
                            None,
                            0.5,
                            0.5
                        )

                        pcm_bytes = (audio_out * 32767).astype(np.int16).tobytes()

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
