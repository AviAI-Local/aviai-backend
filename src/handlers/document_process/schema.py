from pydantic import BaseModel

class DocumentLLMResp(BaseModel):
    scenario_name: str
    scenario_summary: str
    character_name: str
    gender: str


class DocumentExtractResp(BaseModel):
    personal_characteristics: str
    scenario: str
    attitude_in_interview: str
    scenario_name: str
    scenario_summary: str
    character_name: str
    gender: str
