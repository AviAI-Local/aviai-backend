from pydantic import BaseModel
from typing import List, Optional


# -------------------------
# INPUT STRUCTURES
# -------------------------

class ConversationEntry(BaseModel):
    timestamp: float
    datetime: str
    user_query: str
    response: str
    user_emotion: str
    voice_instructions: str
    avatar_instructions: str


class ConversationHistoryInput(BaseModel):
    last_updated: Optional[str]
    conversation_history: List[ConversationEntry]


# -------------------------
# LLM OUTPUT STRUCTURES
# -------------------------

class LLMEmotionAnalysis(BaseModel):
    user_emotion_analysis: str


class LLMEmotionAnalysisOutput(BaseModel):
    analysis: List[LLMEmotionAnalysis]


class LLMConversationSummary(BaseModel):
    conversation_summary: str


# -------------------------
# ANALYSIS RESULT STRUCTURES
# -------------------------

class EmotionAnalysisEntry(BaseModel):
    time: str
    user_emotion_analysis: str


class ConversationAnalysisOutput(BaseModel):
    analysis: List[EmotionAnalysisEntry]
    summary: str


# -------------------------
# API RESPONSES
# -------------------------

class ConversationAnalysisCombinedResponse(BaseModel):
    analysis: List[EmotionAnalysisEntry]
    summary: str
    analysis_id: str
    pdf_base64: str
    filename: str


class ConversationAnalysisPdfResponse(BaseModel):
    analysis_id: str
    pdf_base64: str
    filename: str


class ConversationAnalysisResponse(BaseModel):
    analysis_id: str
    conversation_history_id: Optional[str]
    summary: str
    analysis: List[EmotionAnalysisEntry]
    pdf_base64: str
    filename: str
    created_at: Optional[str] = None
