import warnings
import numpy as np
import torch
import soundfile as sf
import nltk
from qwen_tts import Qwen3TTSModel

warnings.filterwarnings("ignore")
nltk.download('punkt', quiet=True)


class TextToSpeechService:
    """
    Fast local TTS service using Qwen3-TTS (1.7B CustomVoice model).
    Supports 9 built-in premium voices, style/emotion control via natural language,
    multilingual output (Chinese, English, Japanese, Korean, German, French, etc.).
    No voice cloning in this version (use -Base model for that).
    """

    def __init__(self, device: str | None = None):
        """
        Args:
            device: "cuda", "cpu" or None (auto-detect)
        """
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        print(f"Initializing Qwen3-TTS on device: {self.device}")

        # Load the model (downloads ~3–4 GB on first run)
        self.model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            device_map=self.device,
            dtype=torch.bfloat16 if self.device.startswith("cuda") else torch.float32,
            attn_implementation="flash_attention_2" if "cuda" in self.device else None,
        )

        # Built-in voices (you can change default or pass per call)
        self.default_voice = "Vivian"  # bright young female, good Chinese/English

        self.sample_rate = 24000  # Qwen3-TTS standard

        print("Qwen3-TTS loaded successfully!")
        print(f"Available voices: {self.model.get_supported_speakers()}")

    def synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,  # ignored (no cloning here)
        exaggeration: float = 0.5,             # ignored
        cfg_weight: float = 0.5,               # ignored
        voice: str | None = None,
        instruct: str = "",                    # e.g. "very angry", "calm and gentle"
    ) -> tuple[int, np.ndarray]:
        """
        Generate speech from text.
        Returns: (sample_rate, 1D float32 numpy array [-1, 1])
        """
        if audio_prompt_path is not None:
            print("Warning: Qwen3-TTS CustomVoice model does not use reference audio here → ignoring.")

        voice = voice or self.default_voice

        # Single text → list for unified API
        wavs, sr = self.model.generate_custom_voice(
            text=[text],
            language="Auto",               # or "Chinese", "English", etc.
            speaker=[voice],
            instruct=[instruct.strip()],
        )

        if not wavs:
            return self.sample_rate, np.array([], dtype=np.float32)

        # wavs is list of np.ndarray (one per input text)
        return sr, wavs[0].astype(np.float32)

    def long_form_synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        silence_sec: float = 0.15,
        voice: str | None = None,
        instruct: str = "",
    ) -> tuple[int, np.ndarray]:
        """
        Split long text into sentences, synthesize each, add short silence between.
        """
        if not text.strip():
            return self.sample_rate, np.array([], dtype=np.float32)

        sentences = nltk.sent_tokenize(text.strip())
        pieces = []
        silence = np.zeros(int(silence_sec * self.sample_rate), dtype=np.float32)

        voice = voice or self.default_voice

        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue

            _, audio = self.synthesize(
                text=sentence,
                audio_prompt_path=audio_prompt_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                voice=voice,
                instruct=instruct,
            )

            pieces.append(audio)

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
        voice: str | None = None,
        instruct: str = "natural and expressive",
    ) -> None:
        """Generate and save a sample WAV file"""
        sr, audio = self.synthesize(
            text=text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=exaggeration,
            voice=voice,
            instruct=instruct,
        )

        if audio.size == 0:
            print("No audio generated.")
            return

        # float32 [-1,1] → int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # shape (channels, time) → here mono
        audio_tensor = torch.from_numpy(audio_int16).unsqueeze(0)

        sf.write(output_path, audio, sr)  # soundfile handles it directly
        print(f"Sample saved → {output_path}")