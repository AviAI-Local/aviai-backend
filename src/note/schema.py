from typing import Dict, Optional
from pydantic import BaseModel

class NoteResponse(BaseModel):
    note_id: str
    session_id: Optional[str] = None
    account_id: str
    title: Optional[str] = None
    note_content: Optional[Dict] = None  
    timestamp: Optional[str] = None

note_example = {
    "note_id": "n1234567-89ab-4cde-f012-3456789abcde",
    "session_id": "abc12345-6789-4def-0123-456789abcdef",
    "account_id": "user_001",
    "title": "Interview Notes",
    "note_content": {
        "key_points": "Key points from the interview",
        "observations": "Observations about the candidate",
        "strengths": "Candidate's strengths",
        "areas_for_improvement": "Areas that need improvement"
    },
    "timestamp": "2025-06-15T21:36:58.427619"
}

note_request_example = {
    "session_id": "abc12345-6789-4def-0123-456789abcdef",
    "account_id": "user_001",
    "title": "Interview Notes",
    "note_content": {
        "key_points": "Key points from the interview",
        "observations": "Observations about the candidate",
        "strengths": "Candidate's strengths",
        "areas_for_improvement": "Areas that need improvement"
    }
}