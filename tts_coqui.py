import nltk
import torch
import warnings
import numpy as np
import torchaudio as ta
from TTS.api import TTS  # ← Coqui TTS main API

warnings.filterwarnings("ignore")  # Clean up general warnings if needed

nltk.download('punkt', quiet=True)  # For sentence tokenization


class TextToSpeechService:
    def __init__(self, device: str | None = None):
        """
        Initializes the TextToSpeechService with Coqui TTS XTTS-v2.

        Args:
            device (str, optional): "cuda", "mps", or "cpu". Auto-detects if None.
        """
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device

        print(f"Loading Coqui XTTS-v2 on device: {self.device}")

        # Load the best zero-shot multilingual model (XTTS-v2)
        self.model = TTS(
            model_name="tts_models/en/ljspeech/vits--neon",
            progress_bar=True,
            gpu=(self.device == "cuda")  # Coqui handles MPS/CPU as non-gpu
        )

        # XTTS-v2 output sample rate is fixed at 24000 Hz
        self.sample_rate = 24000

        # Move model explicitly if needed (Coqui usually handles it)
        if self.device != "cpu":
            self.model.to(self.device)

    def synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,  # ignored in XTTS
    ):
        """
        Synthesizes audio from text using Coqui XTTS-v2.

        Args:
            text (str): Input text.
            audio_prompt_path (str, optional): Reference audio for voice cloning.
            exaggeration (float, optional): Maps to temperature (0.0-1.0 → more variation).
            cfg_weight (float, optional): Ignored (no direct equivalent in XTTS).

        Returns:
            tuple: (sample_rate, numpy_audio_array)
        """
        # Map exaggeration → temperature (0.3 calm → 0.9 expressive)
        temperature = 0.4 + exaggeration * 0.5  # 0.4-0.9 range works well

        # XTTS returns list of numpy arrays (one per sentence if split, but we pass single text)
        wav_list = self.model.tts(
            text=text,
            speaker_wav=audio_prompt_path,  # voice cloning reference
            #language="en",                  # change to "es", "fr", etc. if needed
            temperature=temperature,
            #speaker="Claribel Dervla"
            # Optional: add split_sentences=True for very long text, but we handle it in long_form
        )

        # tts() returns numpy float32 array already in [-1, 1]
        audio_array = np.array(wav_list) if isinstance(wav_list, list) else wav_list

        return self.sample_rate, audio_array

    def long_form_synthesize(
        self,
        text: str,
        audio_prompt_path: str | None = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,  # ignored
    ):
        """
        Handles long text by splitting into sentences + adding short silence.
        """
        pieces = []
        sentences = nltk.sent_tokenize(text)
        silence_duration = 0.25  # seconds of silence between sentences
        silence = np.zeros(int(silence_duration * self.sample_rate))

        for sent in sentences:
            if not sent.strip():
                continue
            _, audio_array = self.synthesize(
                text=sent,
                audio_prompt_path=audio_prompt_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight
            )
            pieces.extend([audio_array, silence.copy()])

        # Remove last silence if present
        if pieces:
            full_audio = np.concatenate(pieces[:-1])  # drop final silence
        else:
            full_audio = np.array([])

        return self.sample_rate, full_audio

    def save_voice_sample(
        self,
        text: str,
        output_path: str,
        audio_prompt_path: str | None = None,
    ):
        """
        Saves a synthesized sample to WAV file (useful for creating new voice prompts).
        """
        _, audio_array = self.synthesize(
            text=text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=0.6,  # moderate expressiveness for samples
        )

        # Coqui returns float32 [-1,1], torchaudio expects float32 or int16
        # Scale to int16 for standard WAV
        audio_int16 = (audio_array * 32767).astype(np.int16)
        ta.save(output_path, torch.from_numpy(audio_int16).unsqueeze(0), self.sample_rate)