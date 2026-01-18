# src/agent/config.py
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AudioSettings(BaseModel):
    sample_rate: int = 24000
    channels: int = 1
    dtype: str = "int16"


class STTSettings(BaseModel):
    whisper_model: str = "base.en"


class LLMSettings(BaseModel):
    model: str = "gemma3"
    base_url: str = "http://localhost:11434"


class TTSSettings(BaseModel):
    default_exaggeration: float = 0.5
    default_cfg_weight: float = 0.5
    save_voice: bool = False
    voices_dir: str = "voices"


class AppSettings(BaseSettings):
    audio: AudioSettings = AudioSettings()
    stt: STTSettings = STTSettings()
    llm: LLMSettings = LLMSettings()
    tts: TTSSettings = TTSSettings()

    class Config:
        env_prefix = "AGENT_"
        env_nested_delimiter = "__"