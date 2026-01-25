import time
from agent.prompt.builder import PromptBuilder
from agent.history.service import get_session_history
from agent.llm.service import LLMService
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

# ── Qwen3-TTS imports ────────────────────────────────────────────────────────
import torch
import soundfile as sf  # only needed if saving files; optional here
from qwen_tts import Qwen3TTSModel
import nltk
nltk.download('punkt', quiet=True)

console = Console()


class Session:
    """Session that manages its own WebSocket connections and lifecycle"""

    _registry = {}

    def __init__(
        self,
        voice: str = "Vivian",          # Default to a good Qwen built-in voice
        instruct: str = "natural and expressive",  # Default style
        llm_provider: str = "lmstudio",
        base_url: str = None,
        model: str = None,
    ):
        self.session_id = str(uuid.uuid4())
        self.voice = voice
        self.instruct = instruct  # Qwen style/emotion control
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

        # Debug LLM config
        console.print(f"[magenta]============ LLM Configuration ============[/magenta]")
        console.print(f"[magenta]Provider: {llm_provider}[/magenta]")
        console.print(f"[magenta]Base URL: {base_url}[/magenta]")
        console.print(f"[magenta]Model: {model}[/magenta]")
        console.print(f"[magenta]===========================================[/magenta]")

        # LLM setup (unchanged)
        prompt = PromptBuilder().build()
        if llm_provider == "lmstudio":
            llm = ChatOpenAI(base_url=base_url, api_key="not-needed", model=model)
            console.print(f"[green]✓ Using LM Studio with model: {model}[/green]")
        else:
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

        # ── Qwen3-TTS initialization ─────────────────────────────────────────────
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
        console.print(f"[blue]Loading Qwen3-TTS on {device} ({dtype})...[/blue]")

        try:
            self.tts_model = Qwen3TTSModel.from_pretrained(
                "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",  # or -Base / -VoiceDesign
                device_map=device,
                dtype=dtype,
                # attn_implementation="flash_attention_2",  # uncomment if flash-attn installed
            )
            console.print(f"[green]✓ Qwen3-TTS loaded successfully! Voice: {self.voice}[/green]")
            console.print(f"Available voices: {self.tts_model.get_supported_speakers()}")
        except Exception as e:
            console.print(f"[red]Failed to load Qwen3-TTS: {e}[/red]")
            raise

        self.sample_rate = 24000  # Qwen3-TTS fixed output rate

        # STT unchanged
        self.stt = FasterWhisperSTT(
            model_size="small",
            silence_db=-45,
            end_silence_sec=1.2,
        )

        Session._registry[self.session_id] = self
        console.print(f"[green]Session {self.session_id} created with Qwen voice={voice}[/green]")

    @classmethod
    def get_by_id(cls, session_id: str) -> Optional["Session"]:
        return cls._registry.get(session_id)

    @classmethod
    async def handle_connect(cls, websocket: WebSocket):
        await websocket.accept()

        try:
            msg = await websocket.receive()
            config = json.loads(msg.get("text", "{}"))
            voice = config.get("voice") or TTS_VOICE
            # Optional: let client pass instruct/style
            instruct = config.get("instruct") or "natural and expressive"
            llm_provider = config.get("llm_provider") or LLM_PROVIDER
            base_url = config.get("base_url") or LLM_BASE_URL
            model = config.get("model") or LLM_MODEL
        except:
            voice = "Vivian"
            instruct = "natural and expressive"
            llm_provider = "ollama"
            base_url = None
            model = None

        session = cls(
            voice=voice,
            instruct=instruct,
            llm_provider=llm_provider,
            base_url=base_url,
            model=model
        )

        await websocket.send_json({
            "type": "session_created",
            "session_id": session.session_id,
            "voice": session.voice
        })

        # Keep-alive loop unchanged...
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                    payload = json.loads(msg.get("text", "{}"))

                    if payload.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                        continue

                    if payload.get("type") == "update_voice":
                        session.voice = payload["voice"]
                        # Optional: update instruct too if sent
                        if "instruct" in payload:
                            session.instruct = payload["instruct"]
                        await websocket.send_json({
                            "type": "voice_updated",
                            "voice": session.voice
                        })

                except asyncio.TimeoutError:
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
        console.print(f"[green]Conversation started for session {self.session_id}[/green]")
        await websocket.send_json({"type": "status", "state": "listening"})

        try:
            while True:
                msg = await websocket.receive()

                if "text" in msg and msg["text"]:
                    payload = json.loads(msg["text"])

                    if payload["type"] == "audio_playback_complete":
                        self.is_speaking = False
                        await websocket.send_json({"type": "status", "state": "listening"})
                        continue

                    if payload["type"] == "end_of_utterance":
                        if not self.buffer:
                            continue

                        audio_np = np.frombuffer(self.buffer, dtype=np.int16).astype(np.float32) / 32768.0
                        self.buffer.clear()

                        text = await asyncio.to_thread(self.stt.transcribe, audio_np)
                        if not text:
                            continue

                        console.print(f"[yellow]{self.session_id} - You:[/yellow] {text}")

                        start = time.perf_counter()
                        response = await asyncio.to_thread(self.llm_service.get_response, text)
                        llm_time = time.perf_counter() - start

                        content = response.response
                        await websocket.send_json({"type": "assistant_text", "content": content})
                        console.print(f"[cyan]{self.session_id} - Assistant:[/cyan] {content}")

                        start = time.perf_counter()

                        # ── Qwen TTS generation ───────────────────────────────────────
                        sr, audio_out = await asyncio.to_thread(
                            self._qwen_synthesize_long,
                            content,
                            voice=self.voice,
                            instruct=self.instruct
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
                        await websocket.send_bytes(pcm_bytes)
                        await websocket.send_json({"type": "status", "state": "speaking"})
                        continue

                if self.is_speaking:
                    continue

                data = msg.get("bytes")
                if data:
                    self.buffer.extend(data)

        except WebSocketDisconnect:
            console.print(f"[red]Conversation ended for session {self.session_id}[/red]")
        except Exception as e:
            console.print(f"[red]Error in conversation for session {self.session_id}: {e}[/red]")

    def _qwen_synthesize_long(
        self,
        text: str,
        voice: str,
        instruct: str = "",
        silence_sec: float = 0.15,
    ) -> tuple[int, np.ndarray]:
        """Split long text into sentences, synthesize, add silence between."""
        if not text.strip():
            return self.sample_rate, np.array([], dtype=np.float32)

        sentences = nltk.sent_tokenize(text.strip())
        pieces = []
        silence = np.zeros(int(silence_sec * self.sample_rate), dtype=np.float32)

        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue

            wavs, sr = self.tts_model.generate_custom_voice(
                text=sentence,
                language="Auto",  # or detect: "English", "Chinese", etc.
                speaker=voice,
                instruct=instruct,
            )

            if wavs:
                pieces.append(wavs[0].astype(np.float32))

            if i < len(sentences) - 1:
                pieces.append(silence.copy())

        if not pieces:
            return self.sample_rate, np.array([], dtype=np.float32)

        full_audio = np.concatenate(pieces)
        return self.sample_rate, full_audio

    def cleanup(self):
        try:
            self.buffer.clear()
            if self.session_id in Session._registry:
                del Session._registry[self.session_id]
                console.print(f"[yellow]Session {self.session_id} cleaned up[/yellow]")
        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")