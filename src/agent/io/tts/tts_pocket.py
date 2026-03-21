import os
import re
import warnings
warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    message=r".*(invalid value|divide by zero|overflow) encountered in matmul.*",
)

import nltk
import numpy as np
from pocket_tts import TTSModel

try:
    from pocket_tts import export_model_state
    _CAN_EXPORT = True
except ImportError:
    _CAN_EXPORT = False

nltk.download('punkt',     quiet=True)
nltk.download('punkt_tab', quiet=True)

# ---------------------------------------------------------------------------
# Emotion detection — keyword scoring (no heavy NLP deps)
# ---------------------------------------------------------------------------

# Each emotion maps to a list of keywords that vote for it.
# The sentence is lower-cased before matching.
_EMOTION_KEYWORDS: dict[str, list[str]] = {
    "Happy": [
        "great", "wonderful", "fantastic", "excellent", "happy", "love",
        "amazing", "excited", "congratulations", "glad", "joy", "good news",
        "thrilled", "perfect", "brilliant", "awesome", "delighted", "celebrate",
    ],
    "Sad": [
        "sorry", "unfortunately", "sad", "miss", "disappoint", "regret",
        "apologize", "apology", "afraid", "unable", "can't help", "cannot",
        "difficult", "hard", "struggle", "failure", "failed",
    ],
    "Angry": [
        "unacceptable", "frustrated", "angry", "wrong", "problem", "issue",
        "terrible", "awful", "absolutely not", "never", "refuse", "demand",
        "outrageous", "ridiculous", "incompetent",
    ],
}

# Punctuation boosts applied on top of keyword scores
_PUNCT_EMOTION_BOOST: dict[str, dict[str, float]] = {
    "!":  {"Happy": 1.5, "Angry": 1.5},
    "?":  {"Sad": 0.5},
}


def _detect_emotion(text: str, available: set[str]) -> str | None:
    """
    Return the best-matching emotion name (must be in *available*), or None
    if no emotion folder was loaded (falls back to default state).
    """
    if not available:
        return None

    lower = text.lower()
    punct = text.rstrip()[-1] if text.rstrip() else ""
    scores: dict[str, float] = {e: 0.0 for e in available}

    for emotion, keywords in _EMOTION_KEYWORDS.items():
        if emotion not in available:
            continue
        for kw in keywords:
            if kw in lower:
                scores[emotion] += 1.0

    # Punctuation boosts
    for emotion, boost in _PUNCT_EMOTION_BOOST.get(punct, {}).items():
        if emotion in scores:
            scores[emotion] += boost

    # Neutral is always available as a fallback (score stays 0 unless absent)
    if "Neutral" in available:
        pass  # its score is 0 — wins only when nothing else matches

    best_emotion = max(scores, key=lambda e: scores[e])
    # Only commit to a non-Neutral emotion if it actually scored
    if scores[best_emotion] == 0 and "Neutral" in available:
        return "Neutral"
    return best_emotion


# ---------------------------------------------------------------------------
# Pause durations (seconds) per trailing punctuation
# ---------------------------------------------------------------------------
_PAUSE = {
    "?":  0.30,
    "!":  0.25,
    ".":  0.22,
    ";":  0.14,
    ",":  0.08,
    "—":  0.08,
    "-":  0.06,
}
_DEFAULT_PAUSE = 0.18

# Amplitude multiplier per trailing punctuation
_GAIN = {
    "!":  1.18,
    "?":  1.08,
    ".":  1.00,
    ";":  0.96,
    ",":  0.92,
    "—":  0.94,
    "-":  0.94,
}
_DEFAULT_GAIN = 1.00

# Pitch-shift factor (< 1 → higher pitch)
_PITCH = {
    "?":  0.975,
    "!":  0.965,
    ".":  1.000,
    ";":  1.000,
    ",":  1.005,
}
_DEFAULT_PITCH = 1.000


# ---------------------------------------------------------------------------
# Audio helpers (pure numpy)
# ---------------------------------------------------------------------------

def _resample_linear(audio: np.ndarray, factor: float) -> np.ndarray:
    if abs(factor - 1.0) < 0.002 or len(audio) == 0:
        return audio
    new_len = max(1, int(len(audio) * factor))
    indices = np.linspace(0, len(audio) - 1, new_len)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


def _compress(audio: np.ndarray, threshold: float = 0.35, ratio: float = 3.5) -> np.ndarray:
    if len(audio) == 0:
        return audio
    abs_a = np.abs(audio)
    out = np.where(
        abs_a > threshold,
        np.sign(audio) * (threshold + (abs_a - threshold) / ratio),
        audio,
    )
    peak_in  = np.max(abs_a)
    peak_out = np.max(np.abs(out))
    if peak_out > 1e-6 and peak_in > 1e-6:
        out *= peak_in / peak_out
    return out.astype(np.float32)


def _apply_fade(audio: np.ndarray, sample_rate: int, ms: int = 6) -> np.ndarray:
    n = min(int(ms * sample_rate / 1000), len(audio) // 4)
    if n < 2:
        return audio
    fade = np.linspace(0.0, 1.0, n, dtype=np.float32)
    audio = audio.copy()
    audio[:n]  *= fade
    audio[-n:] *= fade[::-1]
    return audio


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _trailing_punct(s: str) -> str:
    s = s.rstrip()
    return s[-1] if s else ""


def _split_into_chunks(text: str) -> list[str]:
    """Sentence → clause split for punchier, more natural delivery."""
    sentences = nltk.sent_tokenize(text.strip())
    chunks: list[str] = []
    clause_split = re.compile(r'(?<=[,;—])\s+')
    for sent in sentences:
        parts = clause_split.split(sent.strip())
        chunks.extend(p.rstrip() for p in parts if p.strip())
    return chunks


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TextToSpeechService:
    """
    Pocket TTS service with:
    - Emotion-driven voice states (swap reference audio per sentence)
    - Per-punctuation pitch shift, amplitude & pause variation
    - Full-utterance dynamic compression
    """

    # Paths are resolved relative to this file so they work regardless of CWD.
    # Override via env vars if needed.
    _HERE = os.path.dirname(os.path.abspath(__file__))
    REFS_DIR   = os.getenv("EMOTION_REFERENCES_DIR", os.path.join(_HERE, "Voice_reference"))
    STATES_DIR = os.getenv("EMOTION_STATES_DIR",     os.path.join(_HERE, "Emotional_states"))

    def __init__(self, voice: str = "cosette"):
        self.model = TTSModel.load_model()
        self.sample_rate = self.model.sample_rate

        # Default (non-emotion) state
        self.state = self.model.get_state_for_audio_prompt(voice)

        # Emotion states: {"Happy": state, "Sad": state, ...}
        self._emotion_states: dict[str, object] = {}
        self._load_emotion_states()

    # ------------------------------------------------------------------
    # Emotion state loading
    # ------------------------------------------------------------------

    def _load_emotion_states(self) -> None:
        """
        Load emotion voice states.  Priority per emotion name:
          1. <STATES_DIR>/<Emotion>.safetensors  (pre-compiled, fast)
          2. <REFS_DIR>/<Emotion>.wav            (compile + cache)
        Gracefully skips if neither folder exists.
        """
        os.makedirs(self.STATES_DIR, exist_ok=True)

        # Collect candidate names from both folders
        candidates: set[str] = set()
        if os.path.isdir(self.STATES_DIR):
            for f in os.listdir(self.STATES_DIR):
                name, ext = os.path.splitext(f)
                if ext.lower() == ".safetensors":
                    candidates.add(name)
        if os.path.isdir(self.REFS_DIR):
            for f in os.listdir(self.REFS_DIR):
                name, ext = os.path.splitext(f)
                if ext.lower() in (".wav", ".mp3"):
                    candidates.add(name)

        if not candidates:
            return

        for name in sorted(candidates):
            state_path = os.path.join(self.STATES_DIR, f"{name}.safetensors")
            wav_path_w = os.path.join(self.REFS_DIR,   f"{name}.wav")
            wav_path_m = os.path.join(self.REFS_DIR,   f"{name}.mp3")
            wav_path   = wav_path_w if os.path.exists(wav_path_w) else wav_path_m

            try:
                if os.path.exists(state_path):
                    state = self.model.get_state_for_audio_prompt(state_path)
                    print(f"[TTS] Loaded emotion state: {name}")
                elif os.path.exists(wav_path):
                    state = self.model.get_state_for_audio_prompt(wav_path)
                    if _CAN_EXPORT:
                        export_model_state(state, state_path)
                        print(f"[TTS] Compiled & cached emotion state: {name}")
                    else:
                        print(f"[TTS] Loaded emotion state from wav: {name}")
                else:
                    continue

                self._emotion_states[name] = state

            except Exception as exc:
                print(f"[TTS] Warning — could not load emotion '{name}': {exc}")

        if self._emotion_states:
            print(f"[TTS] {len(self._emotion_states)} emotion(s) ready: "
                  f"{list(self._emotion_states.keys())}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def long_form_synthesize(
        self,
        text: str,
        voice: str | None = None,
        *_,
        **__,
    ):
        if not text.strip():
            return self.sample_rate, np.array([], dtype=np.float32)

        # A caller-supplied voice overrides emotion detection
        base_state = (
            self.model.get_state_for_audio_prompt(voice)
            if voice is not None
            else None
        )
        use_emotion = base_state is None and bool(self._emotion_states)
        available_emotions = set(self._emotion_states.keys())

        chunks = _split_into_chunks(text)
        pieces: list[np.ndarray] = []

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            # Pick state: emotion-aware > caller voice > default
            if base_state is not None:
                state = base_state
            elif use_emotion:
                emotion = _detect_emotion(chunk, available_emotions)
                state = self._emotion_states.get(emotion) or self.state
            else:
                state = self.state

            # Synthesise
            audio = self.model.generate_audio(state, chunk)
            audio_np = audio.detach().cpu().numpy().astype(np.float32)

            punct = _trailing_punct(chunk)

            # 1. Subtle pitch shift per punctuation
            audio_np = _resample_linear(audio_np, _PITCH.get(punct, _DEFAULT_PITCH))

            # 2. Amplitude weight per punctuation
            audio_np = audio_np * _GAIN.get(punct, _DEFAULT_GAIN)

            # 3. Fade edges to prevent clicks
            audio_np = _apply_fade(audio_np, self.sample_rate)

            pieces.append(audio_np)

            # 4. Pause between chunks
            if i < len(chunks) - 1:
                pause_sec = _PAUSE.get(punct, _DEFAULT_PAUSE)
                pieces.append(np.zeros(int(pause_sec * self.sample_rate), dtype=np.float32))

        if not pieces:
            return self.sample_rate, np.array([], dtype=np.float32)

        full_audio = np.concatenate(pieces)

        # 5. Full-utterance dynamic compression for emotional presence
        full_audio = _compress(full_audio)
        full_audio = np.clip(full_audio, -1.0, 1.0)

        return self.sample_rate, full_audio
