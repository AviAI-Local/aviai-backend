from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Dict, Optional
from .service import NoteService
from database.config import get_db
from database.model import Session as DBSession
from note.schema import NoteResponse, note_example, note_request_example
router = APIRouter()

#  GET /notes -> GET/
@router.get("/", response_model=List[NoteResponse], responses={200: {"content": {"application/json": {"example": [note_example]}}}})
async def get_all_notes(db: DBSession = Depends(get_db)):
    """Get all available notes."""
    service = NoteService(db)
    notes = service.get_all_notes()
    return [note.to_dict() for note in notes]

# GET /notes/{note_id} -> GET/{note_id}
@router.get("/{note_id}", response_model=NoteResponse, responses={200: {"content": {"application/json": {"example": note_example}}}})
async def get_note(note_id: str, db: DBSession = Depends(get_db)):
    """Get a specific note by ID."""
    service = NoteService(db)
    note = service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note.to_dict()

# GET /notes/session/{session_id} -> GET/session/{session_id}
@router.get("/session/{session_id}", response_model=List[NoteResponse], responses={200: {"content": {"application/json": {"example": [note_example]}}}})
async def get_notes_by_session(session_id: str, db: DBSession = Depends(get_db)):
    """Get all notes for a specific session."""
    service = NoteService(db)
    try:
        notes = service.get_notes_by_session(session_id)
        return [note.to_dict() for note in notes]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/account/{account_id}", response_model=List[Dict])
async def get_notes_by_account(account_id: str, db: DBSession = Depends(get_db)):
    """Get all notes for a specific account."""
    service = NoteService(db)
    try:
        notes = service.get_notes_by_account(account_id)
        return [note.to_dict() for note in notes]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/search/by-scenario-name", response_model=List[NoteResponse])
async def search_note_by_scenario_name(
    scenario_name: str,
    db: DBSession = Depends(get_db)
):
    service = NoteService(db)
    notes = service.search_by_scenario_name(scenario_name)
    return [NoteResponse(**note.to_dict()) for note in notes]

# POST /notes -> POST/create
@router.post(
    "/create",
    response_model=NoteResponse,
    responses={200: {"content": {"application/json": {"example": note_example}}}}
)
async def create_note(
    note_data: Dict = Body(..., example=note_request_example),
    db: DBSession = Depends(get_db)
):
    """Create a new note."""
    service = NoteService(db)
    return service.create_note_with_validation(note_data)

# DELETE /notes/{note_id} -> DELETE/delete/{note_id}
@router.delete("/delete/{note_id}")
async def delete_note(note_id: str, db: DBSession = Depends(get_db)):
    """Delete a note."""
    service = NoteService(db)
    if not service.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted successfully"}

# PATCH /notes/{note_id} -> PATCH/update/{note_id}
@router.patch(
    "/update/{note_id}",
    response_model=NoteResponse,
    summary="Update any field(s) of a note",
    description="""
Update one or more fields of a note. Only provided fields will be updated. Returns the updated note.

**Fields:**
- `session_id`: ID of the session (must exist if provided)
- `account_id`: ID of the account (must exist)
- `title`: Title of the note
- `note_content`: JSON object containing the note content

**Note:** The timestamp will be automatically updated to the current time when the note is modified.
""",
    responses={
        200: {"content": {"application/json": {"example": note_example}}},
        404: {"description": "Note not found"}
    }
)
async def update_note(
    note_id: str,
    update_data: Dict = Body(..., example={
        "title": "Updated Interview Notes",
        "note_content": {
            "key_points": "Updated key points from the interview",
            "observations": "Updated observations about the candidate"
        }
    }),
    db: DBSession = Depends(get_db)
):
    """Update a note."""
    service = NoteService(db)
    try:
        updated_note = service.update_note(note_id, update_data)
        return updated_note
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating note: {str(e)}") 