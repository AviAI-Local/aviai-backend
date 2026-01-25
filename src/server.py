from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import asyncio
import json
from rich.console import Console

from langchain_ollama import ChatOllama
from langchain_core.runnables.history import RunnableWithMessageHistory

from agent.prompt.builder import PromptBuilder
from agent.memory.history import get_session_history
from agent.llm.service import LLMService
from agent.io.tts.tts_qwen import TextToSpeechService
from agent.io.stt.faster_whisper import FasterWhisperSTT

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
# Agent initialization
# ======================

console.print("[yellow]Initializing STT...[/yellow]")
stt = FasterWhisperSTT(
    model_size="small",
    silence_db=-45,
    end_silence_sec=1.2,
)
stt.start()

console.print("[yellow]Initializing TTS...[/yellow]")
tts = TextToSpeechService()

console.print("[yellow]Initializing LLM...[/yellow]")
prompt = PromptBuilder().build()
llm = ChatOllama(model="gemma3")
chain = prompt | llm

chat = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

llm_service = LLMService(chat, session_id="default_session")

# ======================
# Audio constants
# ======================

INPUT_SR = 16000
OUTPUT_SR = 24000
BYTES_PER_SAMPLE = 2
#MIN_BYTES = INPUT_SR * BYTES_PER_SAMPLE * PROCESS_SECONDS

def faster_whisper_transcribe(stt: FasterWhisperSTT, audio_np: np.ndarray) -> str:
    segments, _ = stt.model.transcribe(
        audio_np,
        language="en",
        vad_filter=True,
    )
    return " ".join(seg.text for seg in segments).strip()

@app.websocket("/voice")
async def voice_endpoint(websocket: WebSocket):
    await websocket.accept()
    console.print("[green]Client connected[/green]")

    buffer = bytearray()
    is_speaking = False

    await websocket.send_json({
        "type": "status",
        "state": "listening"
    })

    try:
        while True:
            msg = await websocket.receive()

            # ---------- CONTROL MESSAGES ----------
            if "text" in msg and msg["text"]:
                payload = json.loads(msg["text"])

                if payload["type"] == "audio_playback_complete":
                    is_speaking = False
                    await websocket.send_json({
                        "type": "status",
                        "state": "listening"
                    })
                    continue

                if payload["type"] == "end_of_utterance":
                    if not buffer:
                        continue

                    audio_np = (
                        np.frombuffer(buffer, dtype=np.int16)
                        .astype(np.float32) / 32768.0
                    )
                    buffer.clear()

                    text = await asyncio.to_thread(
                        faster_whisper_transcribe,
                        stt,
                        audio_np
                    )

                    if not text:
                        continue

                    console.print(f"[yellow]You:[/yellow] {text}")

                    response = await asyncio.to_thread(
                        llm_service.get_response,
                        text
                    )

                    content = response.response
                    await websocket.send_json({
                        "type": "assistant_text",
                        "content": content
                    })

                    console.print(f"[cyan]Assistant:[/cyan] {content}")

                    sr, audio_out = await asyncio.to_thread(
                        tts.long_form_synthesize,
                        content,
                        None,
                        0.5,
                        0.5
                    )

                    pcm_bytes = (audio_out * 32767).astype(np.int16).tobytes()

                    is_speaking = True
                    await websocket.send_bytes(pcm_bytes)
                    await websocket.send_json({
                        "type": "status",
                        "state": "speaking"
                    })
                    continue

            # ---------- AUDIO ----------
            if is_speaking:
                continue

            data = msg.get("bytes")
            if data:
                buffer.extend(data)

    except WebSocketDisconnect:
        console.print("[red]Client disconnected[/red]")
