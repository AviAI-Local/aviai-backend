"""
Data models for performance analysis API
Handles conversion from session JSON format to evaluation format
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ===============================
# Input Models (Session Format)
# ===============================

class SessionContent(BaseModel):
    """Single interaction in the session"""
    timestamp: float
    datetime: str
    user_query: str
    response: str
    user_emotion: str = "default"
    voice_instructions: str = ""
    avatar_instructions: str = ""

class SessionData(BaseModel):
    """Complete session data from frontend"""
    session_id: str
    content: List[SessionContent]
    timestamp: str

# ===============================
# Evaluation Input Models
# ===============================

class TranscriptItem(BaseModel):
    """Formatted transcript item for evaluation"""
    speaker: Literal["user", "bot"]
    text: str
    ts: Optional[str] = None

class EmotionPoint(BaseModel):
    """Emotion data point for evaluation"""
    ts: Optional[str] = None
    emotion_label: str

class EvaluationInput(BaseModel):
    """Formatted input for the CI evaluation engine"""
    transcript: List[TranscriptItem]
    emotions: List[EmotionPoint]

# ===============================
# Output Models (from demo.py)
# ===============================

class CIPhases(BaseModel):
    """Cognitive Interview phases assessment"""
    rapport_safety: bool
    context_reinstatement: bool
    free_recall: bool
    varied_focused_retrieval: bool
    closure: bool

class Behaviors(BaseModel):
    """Behavioral assessment results"""
    active_listening: Literal["good", "fair", "poor", "absent"]
    neutral_language: Literal["good", "fair", "poor"]
    contamination_risk: Literal["low", "medium", "high"]
    pacing_ok: Literal["good", "fair", "poor"]
    trauma_informed: Literal["good", "fair", "poor"]

class QuantitativeMetrics(BaseModel):
    """Quantitative performance metrics"""
    open_rate: float
    leading_rate: float
    emotion_regulation: float

class InterviewerEvaluation(BaseModel):
    """Complete interviewer evaluation results"""
    questions: List[Dict[str, Any]]
    ci_phases: CIPhases
    behaviors: Behaviors
    quantitative_metrics: QuantitativeMetrics

class Scores(BaseModel):
    """Detailed scoring breakdown"""
    scores: Dict[str, float]
    total: float
    metrics_passed: List[str]
    verdict: Literal["PASS", "BORDERLINE", "FAIL"]

class CoachingTip(BaseModel):
    """Individual coaching recommendation"""
    area: str
    tip: str

class PerformanceAnalysisResult(BaseModel):
    """Complete performance analysis output"""
    session_id: str
    evaluation: InterviewerEvaluation
    scoring: Scores
    coaching: List[CoachingTip]
    analysis_timestamp: str

class PerformanceAnalysisCombinedResponse(BaseModel):
    """Combined response with analysis result and base64 PDF"""
    # JSON Analysis
    session_id: str
    evaluation: InterviewerEvaluation
    scoring: Scores
    coaching: List[CoachingTip]
    analysis_timestamp: str
    # PDF Output
    analysis_id: str
    pdf_base64: str
    filename: str

# ===============================
# Helper Functions
# ===============================

def convert_session_to_evaluation_input(session_data: SessionData) -> EvaluationInput:
    """
    Convert session data format to evaluation input format
    
    Args:
        session_data: Session data from frontend
        
    Returns:
        EvaluationInput ready for the CI evaluation engine
    """
    transcript = []
    emotions = []
    
    for item in session_data.content:
        # Add user query (interviewer)
        transcript.append(TranscriptItem(
            speaker="user",
            text=item.user_query,
            ts=item.datetime
        ))
        
        # Add bot response (interviewee)
        transcript.append(TranscriptItem(
            speaker="bot", 
            text=item.response,
            ts=item.datetime
        ))
        
        # Add emotion data for interviewer
        emotions.append(EmotionPoint(
            ts=item.datetime,
            emotion_label=item.user_emotion
        ))
    
    return EvaluationInput(
        transcript=transcript,
        emotions=emotions
    )

def format_evaluation_result(session_id: str, llm_result, scoring_result, coaching_result) -> PerformanceAnalysisResult:
    """
    Format the evaluation results into the API response format
    
    Args:
        session_id: Original session ID
        llm_result: LLM evaluation result
        scoring_result: Scoring calculation result
        coaching_result: Coaching recommendations
        
    Returns:
        Formatted performance analysis result
    """
    return PerformanceAnalysisResult(
        session_id=session_id,
        evaluation=InterviewerEvaluation(
            questions=llm_result.interviewer.questions,
            ci_phases=CIPhases(**llm_result.interviewer.ci_phases.model_dump()),
            behaviors=Behaviors(**llm_result.interviewer.behaviors.model_dump()),
            quantitative_metrics=QuantitativeMetrics(**llm_result.interviewer.quantitative_metrics.model_dump())
        ),
        scoring=Scores(
            scores=scoring_result.scores,
            total=scoring_result.total,
            metrics_passed=scoring_result.metrics_passed,
            verdict=scoring_result.verdict
        ),
        coaching=[CoachingTip(area=tip["area"], tip=tip["tip"]) for tip in coaching_result],
        analysis_timestamp=datetime.now().isoformat()
    )