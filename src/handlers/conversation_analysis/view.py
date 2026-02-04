from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
import json
import base64
import uuid
from sqlalchemy.orm import Session
import pytz
from datetime import datetime

from .service import analyze_conversation_history, create_pdf_from_analysis
from .model import ConversationAnalysisCombinedResponse
from database.model import ConversationAnalysis as ConversationAnalysisDB
from database.config import get_db
from agent.history.query import ConversationHistoryQueryService
from database.model import ConversationHistory

TIMEZONE = "Asia/Ho_Chi_Minh"


def convert_to_vietnam_time(timestamp):
    if timestamp is None:
        return None
    tz = pytz.timezone(TIMEZONE)
    if timestamp.tzinfo is None:
        timestamp = pytz.utc.localize(timestamp)
    return timestamp.astimezone(tz)


def _save_and_respond(
    analysis_result, conversation_history_id: str, db: Session
) -> ConversationAnalysisCombinedResponse:
    """Generate PDF, persist analysis to DB, and return the combined response."""
    analysis_id = str(uuid.uuid4())
    pdf_bytes = create_pdf_from_analysis(analysis_result, analysis_id)
    pdf_base64 = base64.b64encode(pdf_bytes).decode()
    filename = f"conversation_analysis_{analysis_id}.pdf"

    db_obj = ConversationAnalysisDB(
        analysis_id=analysis_id,
        conversation_history_id=conversation_history_id,
        summary=analysis_result.summary,
        analysis=[a.model_dump() for a in analysis_result.analysis],
        pdf_base64=pdf_base64,
        filename=filename,
    )
    db.add(db_obj)
    db.commit()

    return ConversationAnalysisCombinedResponse(
        analysis=analysis_result.analysis,
        summary=analysis_result.summary,
        analysis_id=analysis_id,
        pdf_base64=pdf_base64,
        filename=filename,
    )


router = APIRouter()


@router.post(
    "/analyze-by-id/{conversation_history_id}",
    response_model=ConversationAnalysisCombinedResponse,
)
async def analyze_conversation_by_id(
    conversation_history_id: str,
    db: Session = Depends(get_db),
):
    query_service = ConversationHistoryQueryService(db)
    conversation = query_service.get_by_id(conversation_history_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation history not found")

    # content may already be list[dict], base64 JSON, or JSON string
    if isinstance(conversation.content, list):
        conversation_content = conversation.content
    else:
        try:
            conversation_content = query_service.decode_content_from_base64(
                conversation.content
            )
        except Exception:
            conversation_content = json.loads(conversation.content)

    analysis_result = await analyze_conversation_history({
        "last_updated": (
            convert_to_vietnam_time(conversation.timestamp).isoformat()
            if conversation.timestamp else None
        ),
        "conversation_history": conversation_content,
    })

    return _save_and_respond(analysis_result, conversation_history_id, db)


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    obj = db.query(ConversationAnalysisDB).filter_by(
        analysis_id=analysis_id
    ).first()

    if not obj:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return obj.to_dict()


@router.post(
    "/analyze",
    response_model=ConversationAnalysisCombinedResponse,
)
async def analyze_conversation_from_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    payload = json.loads(content.decode("utf-8"))

    if "conversation_history" not in payload:
        raise HTTPException(status_code=400, detail="conversation_history is required")

    # 1. CREATE CONVERSATION HISTORY
    conversation_history_id = str(uuid.uuid4())

    conversation = ConversationHistory(
        conversation_history_id=conversation_history_id,
        session_id=f"upload-{conversation_history_id}",
        content=payload["conversation_history"],  # list[dict]
        timestamp=datetime.utcnow(),
    )

    db.add(conversation)
    db.commit()

    # 2. RUN ANALYSIS
    analysis_result = await analyze_conversation_history({
        "last_updated": payload.get("last_updated"),
        "conversation_history": payload["conversation_history"],
    })

    # 3. STORE & RESPOND
    return _save_and_respond(analysis_result, conversation_history_id, db)
