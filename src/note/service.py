from typing import Dict, Optional, List
from database.model import Note, Session as DBSession, Scenario, Account, get_vietnam_time
import uuid
from fastapi import HTTPException
import pytz

class NoteService:
    def __init__(self, db: DBSession):
        self.db = db
    
    def validate_note_data(self, note_data: Dict) -> None:
        """Validate note data and raise appropriate exceptions."""
        # Validate required fields
        required_fields = ["account_id", "note_content"]  
        for field in required_fields:
            if field not in note_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate note_content is a dictionary (JSON object)
        if not isinstance(note_data["note_content"], dict):
            raise HTTPException(status_code=400, detail="Note content must be a JSON object")
        
        # Validate note content has at least one field
        if not note_data["note_content"]:
            raise HTTPException(status_code=400, detail="Note content cannot be empty")
        
        # Validate session exists if session_id is provided
        session_id = note_data.get("session_id")
        if session_id == "":
            session_id = None
        note_data["session_id"] = session_id  # update for later use
        
        if session_id:
            session = self.db.query(DBSession).filter(DBSession.session_id == session_id).first()
            if not session:
                raise HTTPException(status_code=404, detail=f"Session with ID {session_id} does not exist")
        
        # Validate account exists
        account = self.db.query(Account).filter(Account.account_id == note_data["account_id"]).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Account with ID {note_data['account_id']} does not exist")
    
    def create_note_with_validation(self, note_data: Dict) -> Dict:
        """Create note with full validation and return response data."""
        # Validate input data
        self.validate_note_data(note_data)
        
        # Create note
        note = self.create_note(note_data)
        
        # Return response data
        return note.to_dict()
    
    def create_note(self, note_data: Dict) -> Note:
        note = Note(
            note_id=str(uuid.uuid4()),
            session_id=note_data.get("session_id"),
            account_id=note_data["account_id"],
            title=note_data.get("title"),
            note_content=note_data["note_content"],
            timestamp=get_vietnam_time()
        )
        
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_note(self, note_id: str) -> Optional[Note]:
        return self.db.query(Note).filter(Note.note_id == note_id).first()
    
    def get_all_notes(self) -> List[Note]:
        return self.db.query(Note).all()
    
    def get_notes_by_session(self, session_id: str) -> List[Note]:
        # Verify session exists
        session = self.db.query(DBSession).filter(DBSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session with ID {session_id} does not exist")
            
        return self.db.query(Note).filter(Note.session_id == session_id).all()
    
    def get_notes_by_account(self, account_id: str) -> List[Note]:
        # Verify account exists
        account = self.db.query(Account).filter(Account.account_id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Account with ID {account_id} does not exist")
            
        return self.db.query(Note).filter(Note.account_id == account_id).all()
    
    def delete_note(self, note_id: str) -> bool:
        note = self.get_note(note_id)
        if not note:
            return False
            
        self.db.delete(note)
        self.db.commit()
        return True 

def search_by_scenario_name(self, scenario_name: str):
    return (
        self.db.query(Note)
        .join(DBSession, Note.session_id == DBSession.session_id)
        .join(Scenario, DBSession.scenario_id == Scenario.scenario_id)
        .filter(Scenario.scenario_name.ilike(f"%{scenario_name}%"))
        .all()
    )
    
    def validate_update_data(self, update_data: Dict) -> None:
        """Validate update data and raise appropriate exceptions."""
        # Validate note_content is a dictionary (JSON object) if provided
        if "note_content" in update_data:
            if not isinstance(update_data["note_content"], dict):
                raise HTTPException(status_code=400, detail="Note content must be a JSON object")
            
            # Validate note content has at least one field
            if not update_data["note_content"]:
                raise HTTPException(status_code=400, detail="Note content cannot be empty")
        
        # Validate session exists if session_id is being updated
        if "session_id" in update_data:
            session_id = update_data["session_id"]
            if session_id == "":
                session_id = None
            update_data["session_id"] = session_id  # update for later use
            
            if session_id:
                session = self.db.query(DBSession).filter(DBSession.session_id == session_id).first()
                if not session:
                    raise HTTPException(status_code=404, detail=f"Session with ID {session_id} does not exist")
        
        # Validate account exists if account_id is being updated
        if "account_id" in update_data:
            account = self.db.query(Account).filter(Account.account_id == update_data["account_id"]).first()
            if not account:
                raise HTTPException(status_code=404, detail=f"Account with ID {update_data['account_id']} does not exist")
    
    def update_note(self, note_id: str, update_data: Dict) -> Optional[Dict]:
        """Update note fields and return updated note data."""
        note = self.get_note(note_id)
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        
        # Validate update data
        self.validate_update_data(update_data)
        
        # Only update fields that exist in the model and are provided
        updatable_fields = ["session_id", "account_id", "title", "note_content"]
        for field in updatable_fields:
            if field in update_data:
                setattr(note, field, update_data[field])
        
        # Update timestamp to current time in Vietnam timezone
        note.timestamp = get_vietnam_time()
        
        self.db.commit()
        self.db.refresh(note)
        return note.to_dict() 