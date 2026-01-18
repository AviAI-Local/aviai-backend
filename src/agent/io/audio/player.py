import sounddevice as sd
import numpy as np


def play_audio(sample_rate: int, audio_array: np.ndarray) -> None:
    """
    Play PCM audio using sounddevice.

    Args:
        sample_rate (int): Audio sample rate (e.g. 16000)
        audio_array (np.ndarray): Float32 PCM audio (-1.0 to 1.0)

    Returns:
        None
    """
    if audio_array.size == 0:
        return

    sd.play(audio_array, sample_rate)
    sd.wait()