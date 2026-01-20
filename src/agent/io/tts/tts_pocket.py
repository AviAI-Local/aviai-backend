import warnings
warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    message=r".*(invalid value|divide by zero|overflow) encountered in matmul.*",
)

import numpy as np
from pocket_tts import TTSModel

class TextToSpeechService:
    def __init__(self, voice: str = "cosette"):
        self.model = TTSModel.load_model()

        # IMPORTANT: use a catalog voice, NOT empty string
        self.state = self.model.get_state_for_audio_prompt(voice)

    def long_form_synthesize(
        self,
        text: str,
        voice: str | None = None,
        *_,
        **__,
    ):
        if voice is not None:
            state = self.model.get_state_for_audio_prompt(voice)
        else:
            state = self.state

        audio = self.model.generate_audio(state, text)
        audio_np = audio.detach().cpu().numpy().astype(np.float32)

        return self.model.sample_rate, audio_np
