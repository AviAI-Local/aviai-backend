import warnings
import numpy as np
import torch
import torchaudio as ta
import nltk
from supertonic import TTS

warnings.filterwarnings("ignore")
nltk.download('punkt', quiet=True)


class TextToSpeechService:
    """
    Fast local TTS service using Supertonic (very lightweight & low-latency).
    Supports only preset voices - no voice cloning.
    """

    AVAILABLE_VOICES = [
        "M1", "M2", "M3", "M4", "M5",     # Male voices
        "F1", "F2", "F3", "F4", "F5"      # Female voices
    ]

    def __init__(self, device: str | None = None):
        """
        Args:
            device: "cuda" or "cpu" (only used for logging/info)
                    Supertonic automatically selects best ONNX provider
        """
        # Auto-detect device for logging only
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        print(f"Initializing Supertonic TTS on device (auto-detected): {self.device}")

        self.model = TTS(auto_download=True)
        self.sample_rate = self.model.sample_rate  # usually 24000

        print("Available preset voices:", self.AVAILABLE_VOICES)

        # Default voice
        self.current_voice = "M5"
        self.voice_style = self.model.get_voice_style(voice_name=self.current_voice)
        print(f"Default voice set to: {self.current_voice}")

    def set_voice(self, voice_name: str) -> None:
        """Change current voice preset"""
        if voice_name not in self.AVAILABLE_VOICES:
            print(f"Voice '{voice_name}' not found.")
            print(f"Available voices: {', '.join(self.AVAILABLE_VOICES)}")
            return

        self.current_voice = voice_name
        self.voice_style = self.model.get_voice_style(voice_name=voice_name)
        print(f"Voice changed to: {voice_name}")

    def synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ) -> tuple[int, np.ndarray]:
        """
        Generate speech from text using Supertonic.
        Ignores: audio_prompt_path (no cloning), exaggeration, cfg_weight

        Returns:
            (sample_rate, audio_array) - audio_array is 1D float32 [-1, 1]
        """
        if audio_prompt_path is not None:
            print("Warning: Supertonic does not support voice cloning.")

        wav, _ = self.model.synthesize(
            text=text,
            voice_style=self.voice_style,
            # language="en"   # uncomment and change if needed (ko, es, pt, fr)
        )

        audio = np.asarray(wav, dtype=np.float32).flatten()

        return self.sample_rate, audio

    def long_form_synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        silence_sec: float = 0.25,
    ) -> tuple[int, np.ndarray]:
        """
        Split long text into sentences, synthesize each, add short silence between.
        """
        if not text.strip():
            return self.sample_rate, np.array([], dtype=np.float32)

        sentences = nltk.sent_tokenize(text.strip())
        pieces = []
        silence = np.zeros(int(silence_sec * self.sample_rate), dtype=np.float32)

        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue

            _, audio = self.synthesize(
                text=sentence,
                audio_prompt_path=audio_prompt_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
            )

            pieces.append(audio)

            # Add silence between sentences, but not after last one
            if i < len(sentences) - 1:
                pieces.append(silence.copy())

        if not pieces:
            return self.sample_rate, np.array([], dtype=np.float32)

        full_audio = np.concatenate(pieces)
        return self.sample_rate, full_audio

    def save_voice_sample(
        self,
        text: str,
        output_path: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.6,
    ) -> None:
        """Generate and save a sample WAV file"""
        sr, audio = self.synthesize(
            text=text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=exaggeration,
        )

        # Convert float32 [-1,1] → int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # torchaudio expects [channels, time]
        audio_tensor = torch.from_numpy(audio_int16).unsqueeze(0)

        ta.save(output_path, audio_tensor, sr)
        print(f"Sample saved → {output_path}")