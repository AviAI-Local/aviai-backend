import warnings
import numpy as np
import torch
import torchaudio as ta
import nltk
from kokoro import KPipeline

warnings.filterwarnings("ignore")
nltk.download('punkt', quiet=True)


class TextToSpeechService:
    """
    Fast local TTS service using Kokoro-82M (82M params, extremely fast & high quality).
    No voice cloning support. Uses preset voices only.
    """

    def __init__(self, device: str | None = None):
        """
        Args:
            device: "cuda", "cpu" or None (auto-detect)
                    Kokoro uses torch, so cuda helps a lot if available
        """
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        print(f"Initializing Kokoro TTS on device: {self.device}")

        # Main pipeline - loads model + tokenizer/phonemizer
        self.pipeline = KPipeline(lang_code="a")  # "a" = American English

        self.sample_rate = 24000  # Kokoro standard output

        print("Kokoro loaded successfully!")

    def synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        voice: str = "af_sarah",           # Default voice - can be overridden
    ) -> tuple[int, np.ndarray]:
        """
        Generate speech from text using Kokoro.
        Ignores: cloning, exaggeration, cfg_weight (not supported)

        Returns:
            (sample_rate, 1D float32 numpy array [-1, 1])
        """
        if audio_prompt_path is not None:
            print("Warning: Kokoro does not support voice cloning → ignoring reference audio.")

        generator = self.pipeline(
            text,
            voice=voice,              # ← you can pass different voice here
            speed=1.0,
            split_pattern=r'\n+'
        )

        audio_chunks = []
        for gs, ps, audio_chunk in generator:
            # Convert torch.Tensor → numpy if needed
            if torch.is_tensor(audio_chunk):
                audio_chunk = audio_chunk.cpu().numpy()
            audio_chunks.append(audio_chunk)

        if not audio_chunks:
            return self.sample_rate, np.array([], dtype=np.float32)

        full_audio = np.concatenate(audio_chunks).astype(np.float32)
        return self.sample_rate, full_audio

    def long_form_synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        silence_sec: float = 0.25,
        voice: str = "af_bella",
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
                voice=voice
            )

            pieces.append(audio)

            # Add silence between sentences (skip after last one)
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
        voice: str = "af_bella",
    ) -> None:
        """Generate and save a sample WAV file"""
        sr, audio = self.synthesize(
            text=text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=exaggeration,
            voice=voice
        )

        # float32 [-1,1] → int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # torchaudio expects shape (channels, time)
        audio_tensor = torch.from_numpy(audio_int16).unsqueeze(0)

        ta.save(output_path, audio_tensor, sr)
        print(f"Sample saved → {output_path}")