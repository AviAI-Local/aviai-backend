from pydantic import BaseModel
from typing import List


class ConversationEntry(BaseModel):
    timestamp: float
    datetime: str
    user_query: str
    response: str
    user_emotion: str
    voice_instructions: str
    avatar_instructions: str


class ConversationHistoryInput(BaseModel):
    last_updated: str
    conversation_history: List[ConversationEntry]


class LLMEmotionAnalysis(BaseModel):
    user_emotion_analysis: str


class LLMEmotionAnalysisOutput(BaseModel):
    analysis: List[LLMEmotionAnalysis]


class LLMConversationSummary(BaseModel):
    conversation_summary: str


class EmotionAnalysisEntry(BaseModel):
    time: str  # Format: "0:30", "1:15", etc.
    user_emotion_analysis: str


class ConversationAnalysisOutput(BaseModel):
    analysis: List[EmotionAnalysisEntry]
    summary: str


class ConversationAnalysisCombinedResponse(BaseModel):
    # JSON Analysis
    analysis: List[EmotionAnalysisEntry]
    summary: str
    # PDF Output
    analysis_id: str
    pdf_base64: str
    filename: str


class ConversationAnalysisPdfResponse(BaseModel):
    analysis_id: str
    pdf_base64: str
    filename: str 