from pydantic import BaseModel

class LLMResponse(BaseModel):
    voice_instructions: str
    avatar_instructions: str
    response: str 