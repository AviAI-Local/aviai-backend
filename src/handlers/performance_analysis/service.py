"""
Performance Analysis Service
Handles the business logic for cognitive interview performance evaluation
"""

from typing import Dict, Any, Optional
import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from database.model import CIPerformanceEvaluation
from .model import (
    SessionData, 
    PerformanceAnalysisResult,
    convert_session_to_evaluation_input,
    format_evaluation_result
)
from .evaluate_ci_performance import evaluate_ci_performance
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
import json

logger = logging.getLogger(__name__)

class PerformanceAnalysisService:
    """Service class for handling performance analysis operations"""
    
    def __init__(self):
        """Initialize the service"""
        pass

    # ------------ File cache helpers ------------
    def _get_cache_dir(self) -> str:
        # Store caches directly in the performance_analysis folder as requested
        base_dir = os.path.dirname(__file__)
        cache_dir = os.path.join(base_dir, "data")
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            pass
        return cache_dir

    def _get_cache_filepath(self, conversation_id: str, user_id: str) -> str:
        filename = f"{conversation_id}_{user_id}.json"
        return os.path.join(self._get_cache_dir(), filename)

    def load_cached_result(self, conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            path = self._get_cache_filepath(conversation_id, user_id)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        except Exception:
            return None

    def save_cached_result(self, conversation_id: str, user_id: str, payload: Dict[str, Any]) -> None:
        try:
            def ensure_jsonable(obj: Any):
                try:
                    # pydantic v2
                    if hasattr(obj, "model_dump"):
                        return obj.model_dump()
                except Exception:
                    pass
                try:
                    # pydantic v1
                    if hasattr(obj, "dict"):
                        return obj.dict()
                except Exception:
                    pass
                if isinstance(obj, dict):
                    return {k: ensure_jsonable(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [ensure_jsonable(v) for v in obj]
                if isinstance(obj, tuple):
                    return [ensure_jsonable(v) for v in obj]
                return obj

            path = self._get_cache_filepath(conversation_id, user_id)
            serializable = ensure_jsonable(payload)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write cache file {path}: {e}")

    # ------------ DB lookup helpers ------------
    def find_evaluation_id(self, db: Session, user_id: str, conversation_id: str) -> Optional[str]:
        try:
            rec = (
                db.query(CIPerformanceEvaluation)
                .filter(
                    CIPerformanceEvaluation.user_id == user_id,
                    CIPerformanceEvaluation.conversation_id == conversation_id,
                )
                .order_by(CIPerformanceEvaluation.created_at.desc())
                .first()
            )
            return rec.evaluation_id if rec else None
        except Exception:
            return None
    
    async def analyze_session_performance(
        self, 
        session_data: Dict[str, Any], 
        model: str = "gpt-4o-mini"
    ) -> PerformanceAnalysisResult:
        """
        Analyze the performance of a cognitive interview session
        
        Args:
            session_data: Session data in JSON format (like demo.json)
            model: LLM model to use for evaluation
            
        Returns:
            Complete performance analysis result
            
        Raises:
            ValueError: If session data is invalid
            Exception: If evaluation fails
        """
        try:
            # Parse and validate input data
            logger.info(f"Starting performance analysis for session")
            session = SessionData(**session_data)
            
            # Convert to evaluation format
            evaluation_input = convert_session_to_evaluation_input(session)
            
            # Validate we have enough data
            if len(evaluation_input.transcript) < 2:
                raise ValueError("Insufficient conversation data for analysis. Need at least one interviewer-interviewee exchange.")
            
            # Check for interviewer questions
            interviewer_turns = [item for item in evaluation_input.transcript if item.speaker == "user"]
            if len(interviewer_turns) == 0:
                raise ValueError("No interviewer questions found in the session data.")
            
            logger.info(f"Found {len(interviewer_turns)} interviewer turns and {len(evaluation_input.emotions)} emotion points")
            
            # Convert to the format expected by the evaluation engine
            transcript_dicts = [item.model_dump() for item in evaluation_input.transcript]
            emotion_dicts = [item.model_dump() for item in evaluation_input.emotions]
            
            # Run the evaluation
            logger.info("Running CI performance evaluation...")
            evaluation_result = evaluate_ci_performance(
                transcript=transcript_dicts,
                emotions=emotion_dicts,
                model=model
            )
            
            # Format the results
            result = format_evaluation_result(
                session_id=session.session_id,
                llm_result=evaluation_result.llm,
                scoring_result=evaluation_result.scoring,
                coaching_result=evaluation_result.coaching
            )
            
            logger.info(f"Analysis completed. Score: {result.scoring.total}/100, Verdict: {result.scoring.verdict}")
            return result
            
        except ValueError as ve:
            logger.error(f"Validation error in performance analysis: {ve}")
            raise ve
        except Exception as e:
            logger.error(f"Error in performance analysis: {e}")
            raise Exception(f"Performance analysis failed: {str(e)}")
    
    def validate_session_data(self, session_data: Dict[str, Any]) -> bool:
        """
        Validate session data format
        
        Args:
            session_data: Raw session data
            
        Returns:
            True if valid, False otherwise
        """
        try:
            session = SessionData(**session_data)
            
            # Check minimum requirements
            if len(session.content) < 1:
                return False
                
            # Check for at least one user query
            has_user_query = any(item.user_query.strip() for item in session.content)
            if not has_user_query:
                return False
                
            return True
        except Exception:
            return False
    
    def get_analysis_summary(self, result: PerformanceAnalysisResult) -> Dict[str, Any]:
        """
        Get a summary of the analysis results
        
        Args:
            result: Complete analysis result
            
        Returns:
            Summary dictionary with key metrics
        """
        return {
            "session_id": result.session_id,
            "overall_score": result.scoring.total,
            "verdict": result.scoring.verdict,
            "metrics_passed": len(result.scoring.metrics_passed),
            "total_metrics": 10,  # A1-C10
            "coaching_areas": len(result.coaching),
            "key_strengths": result.scoring.metrics_passed,
            "improvement_areas": [tip.area for tip in result.coaching[:3]],  # Top 3 areas
            "question_analysis": {
                "total_questions": len(result.evaluation.questions),
                "open_rate": result.evaluation.quantitative_metrics.open_rate,
                "leading_rate": result.evaluation.quantitative_metrics.leading_rate
            },
            "ci_phases_completed": sum([
                result.evaluation.ci_phases.rapport_safety,
                result.evaluation.ci_phases.context_reinstatement, 
                result.evaluation.ci_phases.free_recall,
                result.evaluation.ci_phases.varied_focused_retrieval,
                result.evaluation.ci_phases.closure
            ]),
            "analysis_timestamp": result.analysis_timestamp
        }
    
    def save_evaluation_to_database(
        self, 
        db: Session, 
        result: PerformanceAnalysisResult,
        user_id: str,
        conversation_id: str
    ) -> str:
        """
        Save evaluation results to the database
        
        Args:
            db: Database session
            result: Complete analysis result
            user_id: ID of the user being evaluated
            conversation_id: ID of the conversation being evaluated
            
        Returns:
            evaluation_id: The ID of the saved evaluation record
        """
        try:
            # Generate unique evaluation ID
            evaluation_id = str(uuid.uuid4())
            
            # Create evaluation record
            evaluation_record = CIPerformanceEvaluation(
                evaluation_id=evaluation_id,
                user_id=user_id,
                conversation_id=conversation_id,
                session_id=result.session_id,
                
                # Individual weight scores
                a1_score=result.scoring.scores.get("A1", 0.0),
                a2_score=result.scoring.scores.get("A2", 0.0),
                a3_score=result.scoring.scores.get("A3", 0.0),
                a4_score=result.scoring.scores.get("A4", 0.0),
                a5_score=result.scoring.scores.get("A5", 0.0),
                b6_score=result.scoring.scores.get("B6", 0.0),
                b7_score=result.scoring.scores.get("B7", 0.0),
                b8_score=result.scoring.scores.get("B8", 0.0),
                c9_score=result.scoring.scores.get("C9", 0.0),
                c10_score=result.scoring.scores.get("C10", 0.0),
                
                # Total score and verdict
                total_score=result.scoring.total,
                verdict=result.scoring.verdict,
                
                # CI Phases
                rapport_safety=result.evaluation.ci_phases.rapport_safety,
                context_reinstatement=result.evaluation.ci_phases.context_reinstatement,
                free_recall=result.evaluation.ci_phases.free_recall,
                varied_focused_retrieval=result.evaluation.ci_phases.varied_focused_retrieval,
                closure=result.evaluation.ci_phases.closure,
                
                # Quantitative metrics
                open_rate=result.evaluation.quantitative_metrics.open_rate,
                leading_rate=result.evaluation.quantitative_metrics.leading_rate,
                emotion_regulation=result.evaluation.quantitative_metrics.emotion_regulation,
                
                # Behavioral assessments
                active_listening=result.evaluation.behaviors.active_listening,
                neutral_language=result.evaluation.behaviors.neutral_language,
                contamination_risk=result.evaluation.behaviors.contamination_risk,
                pacing_ok=result.evaluation.behaviors.pacing_ok,
                trauma_informed=result.evaluation.behaviors.trauma_informed,
                
                # Question classifications and coaching feedback
                question_classifications=result.evaluation.questions,
                coaching_feedback=[tip.model_dump() for tip in result.coaching] if result.coaching else None,
                
                # Timestamps
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Save to database
            db.add(evaluation_record)
            db.commit()
            db.refresh(evaluation_record)
            
            logger.info(f"Saved evaluation {evaluation_id} to database for user {user_id}")
            return evaluation_id
            
        except Exception as e:
            logger.error(f"Error saving evaluation to database: {e}")
            db.rollback()
            raise Exception(f"Failed to save evaluation to database: {str(e)}")
    
    def get_evaluation_by_id(self, db: Session, evaluation_id: str) -> Optional[CIPerformanceEvaluation]:
        """
        Retrieve an evaluation by its ID
        
        Args:
            db: Database session
            evaluation_id: ID of the evaluation to retrieve
            
        Returns:
            CIPerformanceEvaluation object or None if not found
        """
        try:
            return db.query(CIPerformanceEvaluation).filter(
                CIPerformanceEvaluation.evaluation_id == evaluation_id
            ).first()
        except Exception as e:
            logger.error(f"Error retrieving evaluation {evaluation_id}: {e}")
            return None
    
    def get_evaluations_by_user(self, db: Session, user_id: str, limit: int = 10) -> list[CIPerformanceEvaluation]:
        """
        Retrieve evaluations for a specific user
        
        Args:
            db: Database session
            user_id: ID of the user
            limit: Maximum number of evaluations to return
            
        Returns:
            List of CIPerformanceEvaluation objects
        """
        try:
            return db.query(CIPerformanceEvaluation).filter(
                CIPerformanceEvaluation.user_id == user_id
            ).order_by(CIPerformanceEvaluation.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error retrieving evaluations for user {user_id}: {e}")
            return []

# Service instance
performance_analysis_service = PerformanceAnalysisService()


def create_pdf_from_performance_result(
    result: PerformanceAnalysisResult,
    analysis_id: Optional[str] = None
) -> bytes:
    """Create a PDF report from a PerformanceAnalysisResult.

    The PDF includes:
    - Title and basic metadata
    - Overall score and verdict
    - Scoring breakdown
    - CI phases overview
    - Behavioral assessment
    - Quantitative metrics
    - Question classifications (trimmed)
    - Coaching recommendations
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=30,
        alignment=1,
        textColor=colors.darkblue,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=18,
        textColor=colors.darkblue,
    )
    normal_style = ParagraphStyle(
        "NormalText",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=4,
    )
    field_style = ParagraphStyle(
        "FieldText",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        leftIndent=20,
        spaceAfter=2,
    )

    # Title
    story.append(Paragraph("Cognitive Interview Performance Report", title_style))
    story.append(Spacer(1, 16))

    # Metadata
    story.append(Paragraph("Report Information", heading_style))
    story.append(Paragraph(f"<b>Session ID:</b> {result.session_id}", normal_style))
    if analysis_id:
        story.append(Paragraph(f"<b>Analysis ID:</b> {analysis_id}", normal_style))
    story.append(Paragraph(f"<b>Analysis Timestamp:</b> {result.analysis_timestamp}", normal_style))
    story.append(Spacer(1, 10))

    # Overall score
    story.append(Paragraph("Overall Result", heading_style))
    story.append(Paragraph(f"<b>Total Score:</b> {result.scoring.total:.2f} / 100", normal_style))
    story.append(Paragraph(f"<b>Verdict:</b> {result.scoring.verdict}", normal_style))
    if result.scoring.metrics_passed:
        story.append(
            Paragraph(
                f"<b>Metrics Passed:</b> {', '.join(result.scoring.metrics_passed)}",
                normal_style,
            )
        )

    # Scoring breakdown
    story.append(Paragraph("Scoring Breakdown", heading_style))
    for code, points in result.scoring.scores.items():
        story.append(Paragraph(f"<b>{code}</b>: {points:.2f}", field_style))

    # CI Phases
    story.append(Paragraph("CI Phases", heading_style))
    phases = result.evaluation.ci_phases
    story.append(Paragraph(f"Rapport & Safety: {'Yes' if phases.rapport_safety else 'No'}", field_style))
    story.append(Paragraph(f"Context Reinstatement: {'Yes' if phases.context_reinstatement else 'No'}", field_style))
    story.append(Paragraph(f"Free Recall: {'Yes' if phases.free_recall else 'No'}", field_style))
    story.append(Paragraph(f"Varied Focused Retrieval: {'Yes' if phases.varied_focused_retrieval else 'No'}", field_style))
    story.append(Paragraph(f"Closure: {'Yes' if phases.closure else 'No'}", field_style))

    # Behaviors
    story.append(Paragraph("Behavioral Assessment", heading_style))
    behaviors = result.evaluation.behaviors
    story.append(Paragraph(f"Active Listening: {behaviors.active_listening}", field_style))
    story.append(Paragraph(f"Neutral Language: {behaviors.neutral_language}", field_style))
    story.append(Paragraph(f"Contamination Risk: {behaviors.contamination_risk}", field_style))
    story.append(Paragraph(f"Pacing: {behaviors.pacing_ok}", field_style))
    story.append(Paragraph(f"Trauma-informed: {behaviors.trauma_informed}", field_style))

    # Quantitative metrics
    story.append(Paragraph("Quantitative Metrics", heading_style))
    qm = result.evaluation.quantitative_metrics
    story.append(Paragraph(f"Open Question Rate: {qm.open_rate:.2%}", field_style))
    story.append(Paragraph(f"Leading Question Rate: {qm.leading_rate:.2%}", field_style))
    story.append(Paragraph(f"Emotion Regulation: {qm.emotion_regulation:.2%}", field_style))

    # Questions
    if result.evaluation.questions:
        story.append(Paragraph("Question Classification (all)", heading_style))
        for idx, q in enumerate(result.evaluation.questions, start=1):
            text = q.get("text", "")
            label = q.get("label", "")
            story.append(Paragraph(f"{idx}. {text} <i>[{label}]</i>", field_style))

    # Coaching
    if result.coaching:
        story.append(Paragraph("Coaching Recommendations", heading_style))
        for tip in result.coaching:
            story.append(Paragraph(f"<b>{tip.area}</b>", field_style))
            story.append(Paragraph(f"{tip.tip}", field_style))

    # Disclaimer
    story.append(Spacer(1, 20))
    disclaimer_style = ParagraphStyle(
        "DisclaimerText",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=10,
        alignment=1,  # Center alignment
        textColor=colors.grey
    )
    story.append(Paragraph("This content is for reference only, for more accurate assessment please contact the lecturer.", disclaimer_style))

    doc.build(story)
    return buffer.getvalue()


def create_pdf_from_cached_payload(
    cached_payload: Dict[str, Any],
    analysis_id: Optional[str] = None
) -> bytes:
    """Create a PDF report directly from cached payload (dict), avoiding model reconstruction."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=30,
        alignment=1,
        textColor=colors.darkblue,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=18,
        textColor=colors.darkblue,
    )
    normal_style = ParagraphStyle(
        "NormalText",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=4,
    )
    field_style = ParagraphStyle(
        "FieldText",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        leftIndent=20,
        spaceAfter=2,
    )

    detailed = cached_payload.get("detailed_result", {})
    evaluation = detailed.get("evaluation", {})
    scoring = detailed.get("scoring", {})
    coaching = detailed.get("coaching", [])
    session_id = cached_payload.get("session_id")
    analysis_timestamp = detailed.get("analysis_timestamp")

    story.append(Paragraph("Cognitive Interview Performance Report", title_style))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Report Information", heading_style))
    story.append(Paragraph(f"<b>Session ID:</b> {session_id}", normal_style))
    if analysis_id:
        story.append(Paragraph(f"<b>Analysis ID:</b> {analysis_id}", normal_style))
    story.append(Paragraph(f"<b>Analysis Timestamp:</b> {analysis_timestamp}", normal_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Overall Result", heading_style))
    total = scoring.get("total", 0)
    verdict = scoring.get("verdict", "")
    metrics_passed = scoring.get("metrics_passed", [])
    story.append(Paragraph(f"<b>Total Score:</b> {total:.2f} / 100", normal_style))
    story.append(Paragraph(f"<b>Verdict:</b> {verdict}", normal_style))
    if metrics_passed:
        story.append(Paragraph(f"<b>Metrics Passed:</b> {', '.join(metrics_passed)}", normal_style))

    story.append(Paragraph("Scoring Breakdown", heading_style))
    for code, points in (scoring.get("scores", {}) or {}).items():
        try:
            points_f = float(points)
        except Exception:
            points_f = 0.0
        story.append(Paragraph(f"<b>{code}</b>: {points_f:.2f}", field_style))

    story.append(Paragraph("CI Phases", heading_style))
    phases = evaluation.get("ci_phases", {})
    story.append(Paragraph(f"Rapport & Safety: {'Yes' if phases.get('rapport_safety') else 'No'}", field_style))
    story.append(Paragraph(f"Context Reinstatement: {'Yes' if phases.get('context_reinstatement') else 'No'}", field_style))
    story.append(Paragraph(f"Free Recall: {'Yes' if phases.get('free_recall') else 'No'}", field_style))
    story.append(Paragraph(f"Varied Focused Retrieval: {'Yes' if phases.get('varied_focused_retrieval') else 'No'}", field_style))
    story.append(Paragraph(f"Closure: {'Yes' if phases.get('closure') else 'No'}", field_style))

    story.append(Paragraph("Behavioral Assessment", heading_style))
    behaviors = evaluation.get("behaviors", {})
    story.append(Paragraph(f"Active Listening: {behaviors.get('active_listening', '')}", field_style))
    story.append(Paragraph(f"Neutral Language: {behaviors.get('neutral_language', '')}", field_style))
    story.append(Paragraph(f"Contamination Risk: {behaviors.get('contamination_risk', '')}", field_style))
    story.append(Paragraph(f"Pacing: {behaviors.get('pacing_ok', '')}", field_style))
    story.append(Paragraph(f"Trauma-informed: {behaviors.get('trauma_informed', '')}", field_style))

    story.append(Paragraph("Quantitative Metrics", heading_style))
    qm = evaluation.get("quantitative_metrics", {})
    try:
        story.append(Paragraph(f"Open Question Rate: {float(qm.get('open_rate', 0))*100:.2f}%", field_style))
    except Exception:
        story.append(Paragraph("Open Question Rate: 0.00%", field_style))
    try:
        story.append(Paragraph(f"Leading Question Rate: {float(qm.get('leading_rate', 0))*100:.2f}%", field_style))
    except Exception:
        story.append(Paragraph("Leading Question Rate: 0.00%", field_style))
    try:
        story.append(Paragraph(f"Emotion Regulation: {float(qm.get('emotion_regulation', 0))*100:.2f}%", field_style))
    except Exception:
        story.append(Paragraph("Emotion Regulation: 0.00%", field_style))

    if evaluation.get("questions"):
        story.append(Paragraph("Question Classification (all)", heading_style))
        for idx, q in enumerate(evaluation.get("questions", []), start=1):
            text = q.get("text", "")
            label = q.get("label", "")
            story.append(Paragraph(f"{idx}. {text} <i>[{label}]</i>", field_style))

    if coaching:
        story.append(Paragraph("Coaching Recommendations", heading_style))
        for tip in coaching:
            area = tip.get("area", "")
            tip_text = tip.get("tip", "")
            story.append(Paragraph(f"<b>{area}</b>", field_style))
            story.append(Paragraph(f"{tip_text}", field_style))

    story.append(Spacer(1, 20))
    disclaimer_style = ParagraphStyle(
        "DisclaimerText",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=10,
        alignment=1,
        textColor=colors.grey,
    )
    story.append(Paragraph("This content is for reference only, for more accurate assessment please contact the lecturer.", disclaimer_style))

    doc.build(story)
    return buffer.getvalue()