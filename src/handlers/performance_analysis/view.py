"""
Performance Analysis API Endpoint
"""

from fastapi import APIRouter, HTTPException, status, Response, Depends
from typing import Dict, Any, Optional
import logging
import json
import uuid
import base64

from .service import performance_analysis_service, create_pdf_from_performance_result, create_pdf_from_cached_payload
from .model import PerformanceAnalysisResult, PerformanceAnalysisCombinedResponse
from sqlalchemy.orm import Session
import pytz
from datetime import datetime
from database.config import get_db
from agent.history.query import ConversationHistoryQueryService
from database.model import CIPerformanceEvaluation
from sqlalchemy import func
from collections import defaultdict

logger = logging.getLogger(__name__)

# router = APIRouter(prefix="/performance-analysis", tags=["Performance Analysis"])
router = APIRouter()


def convert_to_vietnam_time(timestamp):
    """Convert UTC timestamp to Vietnam timezone and return ISO string."""
    if timestamp is None:
        return None
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    if timestamp.tzinfo is None:
        timestamp = pytz.utc.localize(timestamp)
    return timestamp.astimezone(vietnam_tz).isoformat()


# @router.post("/", response_model=PerformanceAnalysisCombinedResponse)
# async def analyze_session_performance(
#     conversation_id: str,
#     model: Optional[str] = "gpt-4o-mini",
#     db: Session = Depends(get_db)
# ) -> PerformanceAnalysisCombinedResponse:
#     """
#     Analyze cognitive interview performance from conversation ID and return both JSON analysis and base64 PDF.
    
#     Args:
#         conversation_id: ID of the conversation to analyze
#         model: LLM model to use for evaluation (optional, defaults to gpt-4o-mini)
        
#     Returns:
#         Complete performance analysis result including:
#         - Session ID
#         - Detailed evaluation (questions, CI phases, behaviors, metrics)
#         - Scoring breakdown (individual scores, total, verdict)
#         - Coaching recommendations
#         - Analysis ID, base64-encoded PDF content, and suggested filename
        
#     Example request body:
#     ```json
#     {
#         "conversation_id": "c9e2d8a7-c73e-438f-8d94-60357d09d3b6"
#     }
#     ```
    
#     Example response:
#     ```json
#     {
#         "session_id": "c9e2d8a7-c73e-438f-8d94-60357d09d3b6",
#         "evaluation": {
#             "questions": [...],
#             "ci_phases": {...},
#             "behaviors": {...},
#             "quantitative_metrics": {...}
#         },
#         "scoring": {
#             "scores": {...},
#             "total": 75.5,
#             "metrics_passed": [...],
#             "verdict": "PASS"
#         },
#         "coaching": [...],
#         "analysis_timestamp": "2025-01-15T10:30:00",
#         "analysis_id": "uuid-here",
#         "pdf_base64": "base64-encoded-pdf-content",
#         "filename": "performance_analysis_session_id.pdf"
#     }
#     ```
#     """
#     try:
#         # Fetch conversation by ID
#         conversation_service = ConversationHistoryService(db)
#         conversation = conversation_service.get_conversation_history(conversation_id)
#         if not conversation:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation history not found")

#         # Parse content (try base64 first, then JSON)
#         try:
#             content_list = conversation_service.decode_content_from_base64(conversation.content)
#         except Exception:
#             try:
#                 if isinstance(conversation.content, str):
#                     content_list = json.loads(conversation.content)
#                 else:
#                     content_list = conversation.content
#             except Exception as e:
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid conversation content format: {str(e)}")

#         if not content_list:
#             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty conversation content")

#         # Build session_data in expected format
#         session_data: Dict[str, Any] = {
#             "session_id": conversation.session_id,
#             "content": content_list,
#             "timestamp": convert_to_vietnam_time(conversation.timestamp) if conversation.timestamp else datetime.now().isoformat()
#         }

#         # Validate input data
#         if not performance_analysis_service.validate_session_data(session_data):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Invalid session data format or insufficient data for analysis"
#             )

#         # Perform analysis
#         result = await performance_analysis_service.analyze_session_performance(
#             session_data=session_data,
#             model=model
#         )

#         # Generate unique analysis ID
#         analysis_id = str(uuid.uuid4())
        
#         # Create PDF from analysis
#         pdf_bytes = create_pdf_from_performance_result(result, analysis_id)
        
#         # Convert PDF to base64
#         pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
#         filename = f"performance_analysis_{result.session_id}.pdf"

#         logger.info(f"Analysis completed for session {result.session_id} - Score: {result.scoring.total}/100, Verdict: {result.scoring.verdict}")
        
#         return PerformanceAnalysisCombinedResponse(
#             session_id=result.session_id,
#             evaluation=result.evaluation,
#             scoring=result.scoring,
#             coaching=result.coaching,
#             analysis_timestamp=result.analysis_timestamp,
#             analysis_id=analysis_id,
#             pdf_base64=pdf_base64,
#             filename=filename
#         )
        
#     except ValueError as ve:
#         logger.error(f"Validation error: {ve}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=str(ve)
#         )
#     except Exception as e:
#         logger.error(f"Analysis error: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Analysis failed: {str(e)}"
#         )


@router.post("/pdf", response_model=PerformanceAnalysisCombinedResponse)
async def analyze_session_performance_pdf(
    conversation_id: str,
    user_id: str,
    model: Optional[str] = "gpt-4o-mini",
    db: Session = Depends(get_db)
):
    """
    Analyze cognitive interview performance from conversation ID, save results to database, and return both JSON analysis and base64 PDF.
    
    Args:
        conversation_id: ID of the conversation to analyze
        user_id: ID of the user being evaluated (required for database storage)
        model: LLM model to use for evaluation (optional, defaults to gpt-4o-mini)
        
    Returns:
        Complete performance analysis result including:
        - Session ID
        - Detailed evaluation (questions, CI phases, behaviors, metrics)
        - Scoring breakdown (individual scores, total, verdict)
        - Coaching recommendations
        - Analysis ID, base64-encoded PDF content, and suggested filename
        
    Note: Results are automatically saved to the database with the provided user_id. Subsequent calls with the same
    conversation_id + user_id will use cached JSON and avoid calling the LLM.
    """
    try:
        # Fetch conversation by ID
        conversation_service = ConversationHistoryQueryService(db)
        conversation = conversation_service.get_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation history not found")

        # Parse content (try base64 first, then JSON)
        try:
            content_list = conversation_service.decode_content_from_base64(conversation.content)
        except Exception:
            try:
                if isinstance(conversation.content, str):
                    content_list = json.loads(conversation.content)
                else:
                    content_list = conversation.content
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid conversation content format: {str(e)}")

        if not content_list:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty conversation content")

        # Build session_data in expected format
        session_data: Dict[str, Any] = {
            "session_id": conversation.session_id,
            "content": content_list,
            "timestamp": convert_to_vietnam_time(conversation.timestamp) if conversation.timestamp else datetime.now().isoformat()
        }

        # Validate input data
        if not performance_analysis_service.validate_session_data(session_data):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session data format or insufficient data for analysis"
            )

        # Try cache first
        cached = performance_analysis_service.load_cached_result(conversation_id, user_id)
        if cached:
            logger.error(f"Using cached result for session {conversation_id}")
            # If cache already stores base64, reuse it to avoid PDF regeneration
            cached_pdf = cached.get("pdf_base64")
            cached_filename = cached.get("filename") or f"performance_analysis_{cached.get('session_id')}.pdf"
            detailed = cached.get("detailed_result", {})
            if cached_pdf:
                return PerformanceAnalysisCombinedResponse(
                    session_id=cached.get("session_id"),
                    evaluation=detailed.get("evaluation"),
                    scoring=detailed.get("scoring"),
                    coaching=detailed.get("coaching"),
                    analysis_timestamp=detailed.get("analysis_timestamp"),
                    analysis_id=str(uuid.uuid4()),
                    pdf_base64=cached_pdf,
                    filename=cached_filename
                )
            # Otherwise generate once from cached JSON and update cache with base64
            analysis_id = str(uuid.uuid4())
            pdf_bytes = create_pdf_from_cached_payload(cached, analysis_id)
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            cached["pdf_base64"] = pdf_base64
            cached["filename"] = cached_filename
            performance_analysis_service.save_cached_result(conversation_id, user_id, cached)
            return PerformanceAnalysisCombinedResponse(
                session_id=cached.get("session_id"),
                evaluation=detailed.get("evaluation"),
                scoring=detailed.get("scoring"),
                coaching=detailed.get("coaching"),
                analysis_timestamp=detailed.get("analysis_timestamp"),
                analysis_id=analysis_id,
                pdf_base64=pdf_base64,
                filename=cached_filename
            )

        # Perform analysis
        result = await performance_analysis_service.analyze_session_performance(
            session_data=session_data,
            model=model
        )

        # Save evaluation to database (ensures an evaluation_id exists)
        evaluation_id = performance_analysis_service.save_evaluation_to_database(
            db=db,
            result=result,
            user_id=user_id,
            conversation_id=conversation_id
        )

        # Cache JSON for subsequent non-PDF calls
        temp_summary = performance_analysis_service.get_analysis_summary(result)
        cache_payload = {
            "evaluation_id": evaluation_id,
            "session_id": result.session_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "summary": temp_summary,
            "detailed_result": {
                "evaluation": result.evaluation,
                "scoring": result.scoring,
                "coaching": result.coaching,
                "analysis_timestamp": result.analysis_timestamp
            }
        }
        # Also include PDF content in cache for full payload reuse next time
        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Create PDF from analysis
        pdf_bytes = create_pdf_from_performance_result(result, analysis_id)
        
        # Convert PDF to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        filename = f"performance_analysis_{result.session_id}.pdf"

        cache_payload["pdf_base64"] = pdf_base64
        cache_payload["filename"] = filename
        performance_analysis_service.save_cached_result(conversation_id, user_id, cache_payload)

        logger.info(f"Analysis completed and saved for session {result.session_id} - Score: {result.scoring.total}/100, Verdict: {result.scoring.verdict}, Evaluation ID: {evaluation_id}")

        return PerformanceAnalysisCombinedResponse(
            session_id=result.session_id,
            evaluation=result.evaluation,
            scoring=result.scoring,
            coaching=result.coaching,
            analysis_timestamp=result.analysis_timestamp,
            analysis_id=analysis_id,
            pdf_base64=pdf_base64,
            filename=filename
        )
    except ValueError as ve:
        logger.error(f"Validation error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


def categorize_percentage_score(score: float) -> str:
    """Categorize percentage score (0.0-1.0) into pass/fair/poor"""
    percentage = score * 100
    if percentage >= 80:
        return "pass"
    elif percentage >= 60:
        return "fair"
    else:
        return "poor"


@router.get("/statistics")
async def get_statistics(
    stat_type: str,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get statistics for CIPerformanceEvaluation data.
    
    Args:
        stat_type: Type of statistics to return. Options:
            - "all": All CIPerformanceEvaluation data in JSON format
            - "verdict": Count of pass/fail/borderline verdicts
            - "emotion_regulation": Categorized emotion regulation statistics
            - "open_rate": Categorized open rate statistics  
            - "a3_scores": A3 score distribution with frequency counts
        user_id: Optional user ID to filter results (if not provided, returns all users)
        
    Returns:
        JSON response based on stat_type parameter
    """
    try:
        # Base query
        query = db.query(CIPerformanceEvaluation)
        
        # Filter by user_id if provided
        if user_id:
            query = query.filter(CIPerformanceEvaluation.user_id == user_id)
        
        if stat_type == "all":
            # Return all CIPerformanceEvaluation data
            evaluations = query.all()
            return {
                "total_evaluations": len(evaluations),
                "evaluations": [eval.to_dict() for eval in evaluations]
            }
            
        elif stat_type == "verdict":
            # Count pass/fail/borderline verdicts
            verdict_counts = query.with_entities(
                CIPerformanceEvaluation.verdict,
                func.count(CIPerformanceEvaluation.verdict)
            ).group_by(CIPerformanceEvaluation.verdict).all()
            
            result = {"pass": 0, "fail": 0, "borderline": 0}
            for verdict, count in verdict_counts:
                if verdict.lower() in result:
                    result[verdict.lower()] = count
                    
            return {
                "verdict_statistics": result,
                "total_evaluations": sum(result.values())
            }
            
        elif stat_type == "emotion_regulation":
            # Categorize emotion regulation scores
            evaluations = query.with_entities(CIPerformanceEvaluation.emotion_regulation).all()
            
            categories = {"pass": 0, "fair": 0, "poor": 0}
            for (score,) in evaluations:
                if score is not None:
                    category = categorize_percentage_score(score)
                    categories[category] += 1
                    
            return {
                "emotion_regulation_statistics": categories,
                "total_evaluations": sum(categories.values()),
                "criteria": {
                    "pass": "≥80%",
                    "fair": "60-79%", 
                    "poor": "<60%"
                }
            }
            
        elif stat_type == "open_rate":
            # Categorize open rate scores
            evaluations = query.with_entities(CIPerformanceEvaluation.open_rate).all()
            
            categories = {"pass": 0, "fair": 0, "poor": 0}
            for (score,) in evaluations:
                if score is not None:
                    category = categorize_percentage_score(score)
                    categories[category] += 1
                    
            return {
                "open_rate_statistics": categories,
                "total_evaluations": sum(categories.values()),
                "criteria": {
                    "pass": "≥80%",
                    "fair": "60-79%",
                    "poor": "<60%"
                }
            }
            
        elif stat_type == "a3_scores":
            # A3 score distribution with frequency counts
            evaluations = query.with_entities(CIPerformanceEvaluation.a3_score).all()
            
            score_frequency = defaultdict(int)
            for (score,) in evaluations:
                if score is not None:
                    # Round to 2 decimal places for grouping
                    rounded_score = round(score, 2)
                    score_frequency[rounded_score] += 1
            
            # Convert to sorted list for better presentation
            score_distribution = [
                {"score": score, "frequency": frequency}
                for score, frequency in sorted(score_frequency.items())
            ]
            
            return {
                "a3_score_distribution": score_distribution,
                "total_evaluations": sum(score_frequency.values()),
                "unique_scores": len(score_frequency)
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stat_type. Must be one of: all, verdict, emotion_regulation, open_rate, a3_scores"
            )
            
    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )