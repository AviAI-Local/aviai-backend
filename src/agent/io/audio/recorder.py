import time
import sounddevice as sd
from queue import Queue
from threading import Event
from rich.console import Console

console = Console()


def record_audio(
    stop_event: Event,
    data_queue: Queue,
    sample_rate: int = 16000,
    channels: int = 1,
    dtype: str = "int16",
) -> None:
    """
    Captures audio data from the user's microphone and pushes raw PCM bytes into a queue.

    Args:
        stop_event (Event): signal to stop recording
        data_queue (Queue): receives audio chunks (bytes)
        sample_rate (int): audio sample rate
        channels (int): number of channels
        dtype (str): numpy dtype (int16)

    Returns:
        None
    """

    def callback(indata, frames, time_info, status):
        if status:
            console.print(f"[yellow]{status}[/yellow]")
        data_queue.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype=dtype,
        callback=callback,
    ):
        while not stop_event.is_set():
            time.sleep(0.1)