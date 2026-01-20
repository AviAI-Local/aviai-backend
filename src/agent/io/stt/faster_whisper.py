import time
import queue
import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

mute_mic = False

class FasterWhisperSTT:
    def __init__(
        self,
        model_size="small",
        device="cpu",
        compute_type="int8",
        samplerate=16000,
        channels=1,
        block_duration=0.5,
        chunk_duration=2.0,
        silence_db=-45,
        end_silence_sec=1.2,
        min_utterance_chars=6,
        language="en",
    ):
        self.samplerate = samplerate
        self.channels = channels
        self.block_duration = block_duration
        self.chunk_duration = chunk_duration

        self.frames_per_block = int(self.samplerate * self.block_duration)
        self.frames_per_chunk = int(self.samplerate * self.chunk_duration)

        self.silence_db = silence_db
        self.end_silence_sec = end_silence_sec
        self.min_utterance_chars = min_utterance_chars
        self.language = language

        self.audio_queue = queue.Queue()
        self._stream = None
        self._running = False

        self._muted = threading.Event()

        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    @staticmethod
    def rms_db(x: np.ndarray) -> float:
        rms = np.sqrt(np.mean(np.square(x)) + 1e-12)
        return 20 * np.log10(rms + 1e-12)

    def _audio_callback(self, indata, frames, t, status):
        if status:
            print(status)

        if self._muted.is_set():
            return

        try:
            self.audio_queue.put_nowait(indata.copy())
        except queue.Full:
            # drop if queue is full (prevents latency buildup)
            pass

    def flush_audio_queue(self):
        """Remove all queued audio blocks."""
        try:
            while True:
                self.audio_queue.get_nowait()
        except queue.Empty:
            pass

    def mute(self):
        """Stop capturing mic audio into the queue (used during TTS playback)."""
        self._muted.set()
        self.flush_audio_queue()

    def unmute(self):
        """Resume capturing mic audio."""
        self.flush_audio_queue()
        self._muted.clear()

    def start(self):
        """Start microphone streaming in the background."""
        if self._running:
            return

        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=self.frames_per_block,
            callback=self._audio_callback,
        )
        self._stream.start()
        self._running = True

    def stop(self):
        """Stop microphone streaming."""
        self._running = False
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None

    def transcribe(self, audio_data: np.array) -> str:
        segments, _ = self.model.transcribe(
            audio_data,
                language=self.language,
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                temperature=0,
            )
        return " ".join(seg.text for seg in segments).strip()

    def listen_once(self) -> str:
        """
        Blocks until the user finishes speaking, then returns the utterance as a string.
        Requires start() to have been called.
        """
        if not self._running:
            raise RuntimeError("Call start() before listen_once().")
        
        while self._muted.is_set():
            time.sleep(0.05)

        audio_buffer = []
        collected_text = ""
        last_voice_time = None

        while True:
            if self._muted.is_set():
                audio_buffer = []
                collected_text = ""
                last_voice_time = None
                self.flush_audio_queue()
                while self._muted.is_set():
                    time.sleep(0.05)
                continue
            block = self.audio_queue.get()
            audio_buffer.append(block)

            # voice activity detection by volume
            block_f32 = block.flatten().astype(np.float32)
            level = self.rms_db(block_f32)
            now = time.time()

            if level >= self.silence_db:
                last_voice_time = now

            total_frames = sum(len(b) for b in audio_buffer)

            # run whisper every chunk_duration seconds of audio
            if total_frames >= self.frames_per_chunk:
                audio_data = np.concatenate(audio_buffer, axis=0)[: self.frames_per_chunk]
                audio_buffer = []

                audio_data = audio_data.flatten().astype(np.float32)

                segments, _ = self.model.transcribe(
                    audio_data,
                    language=self.language,
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    temperature=0,
                )

                new_text = " ".join(seg.text.strip() for seg in segments).strip()
                if new_text:
                    collected_text = (collected_text + " " + new_text).strip()

            # end-of-utterance: silence for N seconds after voice started
            if last_voice_time is not None:
                silent_for = now - last_voice_time
                if (
                    silent_for >= self.end_silence_sec
                    and len(collected_text) >= self.min_utterance_chars
                ):
                    return collected_text.strip()