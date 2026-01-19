import warnings

warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    message=r".*(invalid value|divide by zero|overflow) encountered in matmul.*",
)

import threading
import time
import numpy as np
from queue import Queue
from rich.console import Console

from langchain_ollama import ChatOllama
from langchain_core.runnables.history import RunnableWithMessageHistory

from agent.prompt.builder import PromptBuilder
from agent.memory.history import get_session_history
from agent.io.stt.whisper_stt import WhisperSTT
from agent.io.audio.recorder import record_audio
from agent.io.audio.player import play_audio
from agent.llm.service import LLMService
# from agent.io.tts.tts_koko import TextToSpeechService
from agent.io.tts.tts_pocket import TextToSpeechService
from agent.io.stt.faster_whisper import FasterWhisperSTT
# from agent.io.tts.emotion import analyze_emotion

console = Console()

import warnings

warnings.filterwarnings(
    "ignore",
    message=".*invalid value encountered in matmul.*",
    category=RuntimeWarning,
)

def main():
    stt = FasterWhisperSTT(model_size="small", silence_db=-45, end_silence_sec=1.2)
    stt.start()
    tts = TextToSpeechService()

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

    while True:
        console.input("🎤 Press Enter to start recording, Enter again to stop")

        while True:
            # console.print("Listening for speech... (press Ctrl+C to stop)")
            text = stt.listen_once()
            console.print(f"[yellow]You:[/yellow] {text}")

            with console.status("Generating response...", spinner="dots"):
                start = time.perf_counter()
                response = llm_service.get_response(text)
                content = response.response

                llm_time = time.perf_counter() - start

                start = time.perf_counter()
                sample_rate, audio_array = tts.long_form_synthesize(
                    content,
                    audio_prompt_path=None,
                    exaggeration=0.5,
                    cfg_weight=0.5
                )
                tts_time = time.perf_counter() - start
            
            console.print(f"[dim]LLM time: {llm_time:.2f}s | TTS time: {tts_time:.2f}s[/dim]")
            console.print(f"[cyan]Assistant:[/cyan] {content}")
            console.print(f"Facial expression: {response.avatar_instructions}")

            stt.mute()
            try:
                play_audio(sample_rate, audio_array)  # must block
            finally:
                # time.sleep(0.15)      # small cooldown
                # stt.flush_audio_queue()
                stt.unmute()

if __name__ == "__main__":
    main()