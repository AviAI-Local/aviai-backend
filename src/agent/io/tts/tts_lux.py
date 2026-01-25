import warnings
import numpy as np
import torch
import soundfile as sf
import nltk
import os

warnings.filterwarnings("ignore")
nltk.download('punkt', quiet=True)

from agent.io.tts.zipvoice.zipvoice.luxvoice import LuxTTS


class TextToSpeechService:
    """
    Fast local TTS using LuxTTS – zero-shot voice cloning.
    Outputs 48 kHz float32 audio [-1, 1].
    """

    def __init__(self, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Initializing LuxTTS on {self.device}...")

        self.model = LuxTTS(
            'YatharthS/LuxTTS',
            device=self.device,
            threads=4,
        )
        self.sample_rate = 48000

        print("LuxTTS loaded successfully!")

    def synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        pitch_factor: float = 1.12,   # slightly higher for clarity
        gain: float = 1.35,           # louder but safe
        clarity_boost: bool = True,   # high-shelf EQ to reduce muffled sound
    ) -> tuple[int, np.ndarray]:
        audio_prompt_path = self._validate_reference(audio_prompt_path)
        if not audio_prompt_path:
            return self.sample_rate, np.array([], dtype=np.float32)

        if not text.strip():
            return self.sample_rate, np.array([], dtype=np.float32)

        return self._generate(text, audio_prompt_path, pitch_factor, gain, clarity_boost)

    def long_form_synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        silence_sec: float = 0.15,
        pitch_factor: float = 1.12,
        gain: float = 1.35,
        clarity_boost: bool = True,
    ) -> tuple[int, np.ndarray]:
        audio_prompt_path = self._validate_reference(audio_prompt_path)
        if not audio_prompt_path:
            return self.sample_rate, np.array([], dtype=np.float32)

        if not text.strip():
            return self.sample_rate, np.array([], dtype=np.float32)

        sentences = nltk.sent_tokenize(text.strip())
        pieces = []
        silence = np.zeros(int(silence_sec * self.sample_rate), dtype=np.float32)

        encoded_prompt = self._encode_reference(audio_prompt_path)
        if encoded_prompt is None:
            return self.sample_rate, np.array([], dtype=np.float32)

        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue

            _, wav = self._generate(sentence, audio_prompt_path, encoded_prompt, pitch_factor, gain, clarity_boost)
            if len(wav) > 0:
                pieces.append(wav)

            if i < len(sentences) - 1 and pieces:
                pieces.append(silence.copy())

        if not pieces:
            return self.sample_rate, np.array([], dtype=np.float32)

        full_audio = np.concatenate(pieces)
        return self.sample_rate, full_audio

    def _validate_reference(self, path: str | None) -> str | None:
        if path is None:
            path = r"C:\Users\Cypher\Downloads\en-AU-NatashaNeural.wav"
            print(f"[TTS] Using default reference: {path}")

        if not os.path.exists(path):
            print(f"[TTS ERROR] Reference file missing: {path}")
            return None

        return path

    def _encode_reference(self, path: str):
        try:
            return self.model.encode_prompt(path, rms=0.01)
        except Exception as e:
            print(f"[TTS] Failed to encode reference: {e}")
            return None

    def _generate(
        self,
        text: str,
        audio_prompt_path: str,
        encoded_prompt=None,
        pitch_factor: float = 1.12,
        gain: float = 1.35,
        clarity_boost: bool = True,
    ) -> tuple[int, np.ndarray]:
        try:
            if encoded_prompt is None:
                encoded_prompt = self._encode_reference(audio_prompt_path)
                if encoded_prompt is None:
                    return self.sample_rate, np.array([], dtype=np.float32)

            print(f"[TTS] Generating: '{text[:50]}...'")

            wav = self.model.generate_speech(
                text=text,
                encode_dict=encoded_prompt,
                num_steps=4,
                t_shift=1.0,
                speed=1.0,
                return_smooth=True,
            )

            if wav is None or len(wav) == 0:
                print("[TTS] Empty waveform")
                return self.sample_rate, np.array([], dtype=np.float32)

            # Force clean 1D float32
            if torch.is_tensor(wav):
                wav = wav.cpu().numpy()
            wav = np.squeeze(wav)
            if wav.ndim > 1:
                wav = wav.mean(axis=1)  # mono
            wav = wav.astype(np.float32)

            # Normalize
            max_abs = np.max(np.abs(wav))
            if max_abs > 0:
                wav /= max_abs

            # Pitch shift (higher = clearer / less muffled)
            if pitch_factor != 1.0 and len(wav) > 10:
                new_length = int(len(wav) / pitch_factor)
                if new_length > 0:
                    x_old = np.linspace(0, len(wav) - 1, len(wav))
                    x_new = np.linspace(0, len(wav) - 1, new_length)
                    wav = np.interp(x_new, x_old, wav)

            # Clarity boost: simple high-shelf (boost highs ~4–8 kHz)
            if clarity_boost and len(wav) > 100:
                # Basic high-shelf: boost above ~4000 Hz
                freq = np.fft.rfftfreq(len(wav), 1/self.sample_rate)
                mask = freq > 4000
                fft_wav = np.fft.rfft(wav)
                fft_wav[mask] *= 1.4  # boost highs
                wav = np.fft.irfft(fft_wav)

            # Volume boost
            wav *= gain

            # Final safe normalization
            max_abs = np.max(np.abs(wav))
            if max_abs > 0:
                wav /= max_abs

            print(f"[TTS] Generated {len(wav)/self.sample_rate:.2f}s audio")
            return self.sample_rate, wav

        except Exception as e:
            print(f"[TTS] Generation failed: {e}")
            return self.sample_rate, np.array([], dtype=np.float32)

    def save_voice_sample(
        self,
        text: str,
        output_path: str,
        audio_prompt_path: str | None = None,
        pitch_factor: float = 1.15,
        gain: float = 1.4,
        clarity_boost: bool = True,
    ) -> None:
        sr, audio = self.synthesize(text, audio_prompt_path, pitch_factor, gain)

        if audio.size == 0:
            print("No audio generated – check reference file and logs")
            return

        sf.write(output_path, audio, sr)
        print(f"Sample saved → {output_path}")