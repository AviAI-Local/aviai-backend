from pydantic import BaseModel

class DocumentLLMResp(BaseModel):
    usecase_name: str
    usecase_summary: str
    character_name: str
    gender: str


class DocumentExtractResp(BaseModel):
    personal_characteristics: str
    scenario: str
    attitude_in_interview: str
    usecase_name: str
    usecase_summary: str
    character_name: str
    gender: str
