from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
import json
import base64
import uuid
from sqlalchemy.orm import Session
import pytz
from datetime import datetime

from .service import analyze_conversation_history, create_pdf_from_analysis
from .model import ConversationAnalysisCombinedResponse
from database.config import get_db
from agent.history.query import ConversationHistoryQueryService

def convert_to_vietnam_time(timestamp):
    """Convert UTC timestamp to Vietnam timezone."""
    if timestamp is None:
        return None
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    # If timestamp is naive (no timezone), assume it's UTC
    if timestamp.tzinfo is None:
        timestamp = pytz.utc.localize(timestamp)
    return timestamp.astimezone(vietnam_tz)


router = APIRouter()

# Example responses for documentation
combined_analysis_example = {
    "analysis": [
        {
            "time": "0:00",
            "user_emotion_analysis": "The user displays a neutral tone when asking for self-introduction, indicating a calm and professional approach to the interview process."
        },
        {
            "time": "0:30",
            "user_emotion_analysis": "The user shows signs of anxiety when discussing the incident, which is natural given the stressful nature of the aviation emergency situation."
        }
    ],
    "summary": "The conversation reveals a structured interview process where the interviewee demonstrates professional composure while discussing a challenging aviation incident.",
    "analysis_id": "a1234567-89ab-4cde-f012-3456789abcde",
    "pdf_base64": "JVBERi0xLjQKJcOkw7zDtsO...",
    "filename": "conversation_analysis_a1234567-89ab-4cde-f012-3456789abcde.pdf"
}


@router.post(
    "/analyze-by-id/{conversation_history_id}", 
    response_model=ConversationAnalysisCombinedResponse,
    description="""
Analyze conversation history by conversation ID and return both JSON analysis and base64 PDF.

**Input:** Provide a conversation_id to analyze the conversation history from the database.

**Output:** Returns:
- JSON analysis with emotion insights and summary
- Analysis ID, base64-encoded PDF content, and suggested filename

The PDF includes:
- Conversation Summary
- Emotion Analysis Timeline with detailed insights for each interaction
- Professional formatting suitable for reports

**Example conversation content format:**
```json
[
  {
    "timestamp": 1751770107.068037,
    "datetime": "2025-07-06T09:48:27.068037+07:00",
    "user_query": "can you introduce yourself",
    "response": "I'm Linh, a flight engineer from Hanoi, living in Ho Chi Minh City. I've worked in this field for over 15 years.",
    "user_emotion": "default",
    "voice_instructions": "Speak with a calm and gentle tone.",
    "avatar_instructions": "default"
  }
]
```
""",
    responses={200: {"content": {"application/json": {"example": combined_analysis_example}}}}
)
async def analyze_conversation_by_id(conversation_history_id: str, db: Session = Depends(get_db)):
    """
    Analyze conversation history by conversation ID and return both JSON analysis and base64 PDF
    """
    try:
        # Get conversation history from database
        query_service  = ConversationHistoryQueryService(db)
        conversation = query_service.get_by_id(conversation_history_id)

        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation history not found")
        
        # Handle content parsing - try both JSON and base64 formats
        conversation_content = None
        try:
            # First try to decode as base64 (as per service implementation)
            conversation_content = query_service.decode_content_from_base64(conversation.content)
        except Exception:
            # If base64 decoding fails, try to parse as JSON directly
            try:
                if isinstance(conversation.content, str):
                    conversation_content = json.loads(conversation.content)
                else:
                    # If it's already a list/dict, use it directly
                    conversation_content = conversation.content
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid conversation content format: {str(e)}")
        
        if not conversation_content:
            raise HTTPException(status_code=400, detail="Empty conversation content")
        
        # Convert to the expected format for analysis
        conversation_data = {
            "last_updated": convert_to_vietnam_time(conversation.timestamp).isoformat() if conversation.timestamp else None,
            "conversation_history": conversation_content
        }
        
        # Process the conversation analysis
        analysis_result = await analyze_conversation_history(conversation_data)
        
        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Create PDF from analysis
        pdf_bytes = create_pdf_from_analysis(analysis_result, analysis_id)
        
        # Convert PDF to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        filename = f"conversation_analysis_{analysis_id}.pdf"
        
        return ConversationAnalysisCombinedResponse(
            # JSON Analysis
            analysis=analysis_result.analysis,
            summary=analysis_result.summary,
            # PDF Output
            analysis_id=analysis_id,
            pdf_base64=pdf_base64,
            filename=filename
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post(
    "/analyze", 
    response_model=ConversationAnalysisCombinedResponse,
    description="""
Analyze conversation history from uploaded JSON file and return both JSON analysis and base64 PDF.

**Input:** Upload a JSON file containing conversation history with the required format.

**Output:** Returns:
- JSON analysis with emotion insights and summary
- Analysis ID, base64-encoded PDF content, and suggested filename

The PDF includes:
- Conversation Summary
- Emotion Analysis Timeline with detailed insights for each interaction
- Professional formatting suitable for reports

**Example JSON input format:**
```json
{
  "last_updated": "2025-01-08T10:30:00+07:00",
  "conversation_history": [
    {
      "timestamp": 1751512264.3168352,
      "datetime": "2025-07-03T10:11:04.316835+07:00",
      "user_query": "hello",
      "response": "Hello.",
      "user_emotion": "default",
      "voice_instructions": "Speak with a calm tone.",
      "avatar_instructions": "default"
    }
  ]
}
```
""",
    responses={200: {"content": {"application/json": {"example": combined_analysis_example}}}}
)
async def analyze_conversation(file: UploadFile = File(...)):
    """
    Analyze conversation history from uploaded JSON file and return both JSON analysis and base64 PDF
    """
    try:
        # Read and parse the uploaded file
        content = await file.read()
        conversation_data = json.loads(content.decode('utf-8'))
        
        # Process the conversation analysis
        analysis_result = await analyze_conversation_history(conversation_data)
        
        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Create PDF from analysis
        pdf_bytes = create_pdf_from_analysis(analysis_result, analysis_id)
        
        # Convert PDF to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        filename = f"conversation_analysis_{analysis_id}.pdf"
        
        return ConversationAnalysisCombinedResponse(
            # JSON Analysis
            analysis=analysis_result.analysis,
            summary=analysis_result.summary,
            # PDF Output
            analysis_id=analysis_id,
            pdf_base64=pdf_base64,
            filename=filename
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 