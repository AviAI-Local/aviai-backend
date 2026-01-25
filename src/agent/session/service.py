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

# ── Path setup (critical fix) ───────────────────────────────────────────────
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REF_WAV = os.path.join(BASE_DIR, "127389__acclivity__thetimehascome.wav")

# ── Hardcoded LuxTTS import ─────────────────────────────────────────────────
import sys

from agent.io.tts.zipvoice.zipvoice.luxvoice import LuxTTS

import torch
import nltk
nltk.download('punkt', quiet=True)

console = Console()


class Session:
    """Session with hardcoded LuxTTS + way higher pitch"""

    _registry = {}

    def __init__(
        self,
        voice: str = "default",
        instruct: str = "natural",
        llm_provider: str = "lmstudio",
        base_url: str = None,
        model: str = None,
        reference_audio_path: str = None,
    ):
        self.session_id = str(uuid.uuid4())
        self.voice = voice
        self.instruct = instruct
        self.buffer = bytearray()
        self.is_speaking = False
        self.session_start_time = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

        # Reference fallback
        self.reference_audio_path = reference_audio_path or DEFAULT_REF_WAV

        if not os.path.exists(self.reference_audio_path):
            console.print(
                f"[bold red]Reference audio NOT FOUND:[/bold red] {self.reference_audio_path}\n"
                f"    → Make sure the file is in the same folder as service.py"
            )
        else:
            console.print(f"[cyan]Using reference audio: {self.reference_audio_path}[/cyan]")

        # LuxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        console.print(f"[blue]Loading LuxTTS on {device}...[/blue]")

        self.tts_model = LuxTTS(
            'YatharthS/LuxTTS',
            device=device,
            threads=4,
        )
        self.sample_rate = 48000

        # Pre-encode reference
        self.encoded_prompt = None
        if os.path.exists(self.reference_audio_path):
            try:
                self.encoded_prompt = self.tts_model.encode_prompt(
                    self.reference_audio_path,
                    rms=0.01
                )
                console.print(f"[green]Reference encoded successfully[/green]")
            except Exception as e:
                console.print(f"[red]Failed to encode reference: {e}[/red]")
        else:
            console.print("[yellow]Skipping reference encoding (file missing)[/yellow]")

        # LLM & history
        self.service = ConversationHistoryService(history_response=ConversationHistoryResponse(
            conversation_history_id=str(uuid.uuid4()),
            session_id=self.session_id,
            llm_provider=llm_provider,
            model=model,
            content=[],
            timestamp=self.session_start_time.isoformat()
        ))
        self.service.save_conversation_history()

        prompt = PromptBuilder().build()
        if llm_provider == "lmstudio":
            llm = ChatOpenAI(base_url=base_url, api_key="not-needed", model=model)
            console.print(f"[green]✓ LM Studio – {model}[/green]")
        else:
            llm = ChatOllama(model=model)
            console.print(f"[green]✓ Ollama – {model}[/green]")

        chain = prompt | llm
        chat = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        self.llm_service = LLMService(chat, session_id=self.session_id)

        self.stt = FasterWhisperSTT(
            model_size="small",
            silence_db=-45,
            end_silence_sec=1.2,
        )

        Session._registry[self.session_id] = self
        console.print(
            f"[green]Session {self.session_id} ready "
            f"(ref: {os.path.basename(self.reference_audio_path)})[/green]"
        )

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
            instruct = config.get("instruct") or "natural"
            llm_provider = config.get("llm_provider") or LLM_PROVIDER
            base_url = config.get("base_url") or LLM_BASE_URL
            model = config.get("model") or LLM_MODEL

            ref_path = config.get("reference_audio_path") or DEFAULT_REF_WAV

            session = cls(
                voice=voice,
                instruct=instruct,
                llm_provider=llm_provider,
                base_url=base_url,
                model=model,
                reference_audio_path=ref_path
            )

        except Exception as e:
            console.print(f"[red]Session creation failed: {e}[/red]")
            session = cls(
                voice="default",
                instruct="natural",
                llm_provider="ollama",
                base_url=None,
                model=None,
                reference_audio_path=DEFAULT_REF_WAV   # ← fixed here too
            )

        await websocket.send_json({
            "type": "session_created",
            "session_id": session.session_id,
            "voice": "LuxTTS-cloned"
        })

        # Keep-alive + reference update
        try:
            while True:
                msg = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                payload = json.loads(msg.get("text", "{}"))

                if payload.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if payload.get("type") == "update_voice":
                    if "reference_audio_path" in payload:
                        new_ref = payload["reference_audio_path"]
                        session.reference_audio_path = new_ref
                        if os.path.exists(new_ref):
                            try:
                                session.encoded_prompt = session.tts_model.encode_prompt(new_ref, rms=0.01)
                                console.print(f"[green]Reference updated and encoded: {new_ref}[/green]")
                            except Exception as err:
                                console.print(f"[red]Reference update encode failed: {err}[/red]")
                        else:
                            console.print(f"[red]New reference not found: {new_ref}[/red]")
                    await websocket.send_json({
                        "type": "voice_updated",
                        "voice": "LuxTTS-cloned"
                    })

        except asyncio.TimeoutError:
            await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            console.print(f"[red]Session {session.session_id} disconnected[/red]")
        except Exception as e:
            console.print(f"[red]Keep-alive error: {e}[/red]")
        finally:
            session.cleanup()

    # ───────────────────────────────────────────────────────────────────────────
    # The rest of the class (handle_conversation, _lux_long_synthesize, cleanup)
    # remains unchanged — no path-related issues there
    # ───────────────────────────────────────────────────────────────────────────

    async def handle_conversation(self, websocket: WebSocket):
        console.print(f"[green]Conversation started: {self.session_id}[/green]")
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
                        console.print(f"[cyan]{self.session_id} - AI:[/cyan] {content}")

                        start = time.perf_counter()

                        sr, audio_out = await asyncio.to_thread(
                            self._lux_long_synthesize,
                            content,
                            self.reference_audio_path
                        )
                        tts_time = time.perf_counter() - start

                        if len(audio_out) == 0:
                            console.print("[red]TTS returned empty audio[/red]")
                            continue

                        # Apply way higher pitch post-generation
                        pitch_factor = 2.0  # ← WAY HIGHER (adjust 1.3–1.6)
                        if pitch_factor != 1.0 and len(audio_out) > 10:
                            new_length = int(len(audio_out) / pitch_factor)
                            if new_length > 0:
                                x_old = np.linspace(0, len(audio_out)-1, len(audio_out))
                                x_new = np.linspace(0, len(audio_out)-1, new_length)
                                audio_out = np.interp(x_new, x_old, audio_out)

                        # Louder
                        audio_out *= 1.35
                        max_abs = np.max(np.abs(audio_out))
                        if max_abs > 0:
                            audio_out /= max_abs

                        pcm_bytes = (audio_out * 32767).astype(np.int16).tobytes()

                        console.print(f"[dim]LLM: {llm_time:.2f}s | TTS: {tts_time:.2f}s | Pitch factor: {pitch_factor}[/dim]")

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

                if "bytes" in msg:
                    self.buffer.extend(msg["bytes"])

        except WebSocketDisconnect:
            console.print(f"[red]Conversation ended: {self.session_id}[/red]")
        except Exception as e:
            console.print(f"[red]Conversation error {self.session_id}: {e}[/red]")

    def _lux_long_synthesize(
        self,
        text: str,
        reference_path: str,
        silence_sec: float = 0.15,
    ) -> tuple[int, np.ndarray]:
        if not text.strip() or self.encoded_prompt is None:
            return self.sample_rate, np.array([], dtype=np.float32)

        sentences = nltk.sent_tokenize(text.strip())
        pieces = []
        silence = np.zeros(int(silence_sec * self.sample_rate), dtype=np.float32)

        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue

            wav = self.tts_model.generate_speech(
                text=sentence,
                encode_dict=self.encoded_prompt,
                num_steps=4,
                t_shift=1.0,
                speed=1.0,
                return_smooth=True,
            )

            if wav is not None and len(wav) > 0:
                if torch.is_tensor(wav):
                    wav = wav.cpu().numpy()
                wav = np.squeeze(wav).astype(np.float32)

                max_abs = np.max(np.abs(wav))
                if max_abs > 0:
                    wav /= max_abs

                pieces.append(wav)

            if i < len(sentences) - 1 and pieces:
                pieces.append(silence.copy())

        if not pieces:
            return self.sample_rate, np.array([], dtype=np.float32)

        full_audio = np.concatenate(pieces)
        return self.sample_rate, full_audio

    def cleanup(self):
        try:
            self.buffer.clear()
            Session._registry.pop(self.session_id, None)
            console.print(f"[yellow]Cleaned up session {self.session_id}[/yellow]")
        except Exception as e:
            console.print(f"[red]Cleanup error: {e}[/red]")