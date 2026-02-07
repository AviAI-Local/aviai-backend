from datetime import datetime
from io import BytesIO
import json
import os
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from langchain_core.chat_history import InMemoryChatMessageHistory
from agent.history.schema import ConversationHistoryResponse, ConversationHistoryContent
from agent.llm.schema import LLMResponse
from rich.console import Console
from database.model import ConversationHistory, Session as DBSession, Scenario, Account

_sessions = {}
console = Console()


class ConversationHistoryService:
    def __init__(self, db: DBSession, history_response: Optional[ConversationHistoryResponse] = None):
        self.history_response = history_response
        self.db = db
        self.history_dir = os.path.join(os.path.dirname(__file__), "..", "conversation")
        os.makedirs(self.history_dir, exist_ok=True)

    def get_by_id(self, conversation_id: str) -> Optional[ConversationHistory]:
        return self.db.query(ConversationHistory).filter(ConversationHistory.conversation_history_id == conversation_id).first()
    
    def get_all_conversation_histories(self) -> List[ConversationHistory]:
        return self.db.query(ConversationHistory).all()
    
    def get_conversation_histories_by_session(self, session_id: str) -> List[ConversationHistory]:
        # Verify session exists
        session = self.db.query(DBSession).filter(DBSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session with ID {session_id} does not exist")

        return self.db.query(ConversationHistory).filter(ConversationHistory.session_id == session_id).all()

    def get_conversation_histories_by_account(self, account_id: str) -> List[dict]:
        """Get all conversation histories created by a specific account."""
        # Verify account exists
        account = self.db.query(Account).filter(Account.account_id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Account with ID {account_id} does not exist")

        # Get all sessions belonging to this account
        sessions = self.db.query(DBSession).filter(DBSession.account_id == account_id).all()

        # Return empty list if no sessions found
        if not sessions:
            return []

        # Build a map of session_id -> session for quick lookup
        session_map = {s.session_id: s for s in sessions}
        session_ids = list(session_map.keys())

        # Get all conversation histories for those sessions
        conversations = self.db.query(ConversationHistory).filter(
            ConversationHistory.session_id.in_(session_ids)
        ).all()

        # Build response with llm_provider and model from session
        result = []
        for conv in conversations:
            session = session_map.get(conv.session_id)
            result.append({
                "conversation_history_id": conv.conversation_history_id,
                "session_id": conv.session_id,
                "llm_provider": session.llm_provider if session else None,
                "model": session.model if session else None,
                "content": conv.content,
                "timestamp": conv.timestamp.isoformat() if conv.timestamp else None
            })
        return result

    def create_conversation_history(self) -> bool:
        """Save conversation history to a JSON file"""
        try:
            history_data = {
                "conversation_history_id": self.history_response.conversation_history_id,
                "session_id": self.history_response.session_id,
                "llm_provider": self.history_response.llm_provider,
                "model": self.history_response.model,
                "content": self.history_response.content,
                "timestamp": self.history_response.timestamp
            }

            file_path = os.path.join(self.history_dir, f"{self.history_response.session_id}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            console.print(f"[red]✗ Failed to create conversation history JSON: {e}[/red]")
            return False 

    def add_conversation_entry(self, user_query: str, response_data: LLMResponse, llm_time: float, tts_time: float) -> bool:
        """Add a conversation entry to the history"""
        try:
            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

            entry = ConversationHistoryContent(
                timestamp=now.timestamp(),
                datetime=now.isoformat(),
                user_query=user_query,
                response=response_data.response,
                user_emotion="default",
                voice_instructions=response_data.voice_instructions,
                avatar_instructions=response_data.avatar_instructions,
                llm_time=round(llm_time, 2),
                tts_time=round(tts_time, 2)
            )

            # Append to history_response.content (the source of truth)
            self.history_response.content.append(entry.model_dump())

            success = self.create_conversation_history()
            if success:
                console.print(f"[dim]✓ Conversation entry saved to {self.history_response.session_id}.json[/dim]")
            return success
        except Exception as e:
            console.print(f"[red]✗ Failed to add conversation entry: {e}[/red]")
            return False

    def load_json_file(self) -> ConversationHistoryResponse:
        """Load conversation history from JSON file"""
        file_path = os.path.join(self.history_dir, f"{self.history_response.session_id}.json")
        console.print(f"[dim]Loading JSON from: {file_path}[/dim]")

        if not os.path.exists(file_path):
            console.print(f"[red]✗ File not found: {file_path}[/red]")
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        console.print(f"[dim]✓ JSON loaded, entries count: {len(data.get('content', []))}[/dim]")
        # Pydantic validates structure automatically
        # Raises ValidationError if data doesn't match schema
        return ConversationHistoryResponse(**data)

    def save_conversation_history(self) -> ConversationHistory | None:
        try:
            data = self.load_json_file()
            console.print(f"[dim]Loaded JSON file for session {data.session_id}[/dim]")

            content_as_dicts = [item.model_dump() if hasattr(item, 'model_dump') else item for item in data.content]

            if content_as_dicts == []:
                console.print(f"[red]✗ Conversation history did not save to DB[/red]")
                return

            conversation = ConversationHistory(
                conversation_history_id=data.conversation_history_id,
                session_id=data.session_id,
                content=content_as_dicts,
                timestamp=data.timestamp
            )

            self.db.add(conversation)
            self.db.commit()
            # Don't refresh - session might be closed during cleanup

            console.print(f"[green]✓ Conversation history saved to DB successfully (ID: {conversation.conversation_history_id})[/green]")
            return conversation

        except FileNotFoundError as e:
            console.print(f"[red]✗ Failed to save: JSON file not found - {e}[/red]")
            return None
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass  # Session might already be closed
            console.print(f"[red]✗ Failed to save conversation history to DB: {e}[/red]")
            console.print(f"[yellow]Error type: {type(e).__name__}[/yellow]")
            return None
        
    
    def create_pdf_from_conversation(self, conversation_data: Dict, conversation_id: str) -> bytes:
        """Create a PDF from conversation data with improved layout."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                              rightMargin=0.5*inch, leftMargin=0.5*inch,
                              topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.darkblue
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkblue
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            leading=14
        )
        message_style = ParagraphStyle(
            'MessageStyle',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            leading=14,
            leftIndent=20
        )
        field_style = ParagraphStyle(
            'FieldStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            leading=12,
            leftIndent=30
        )
        
        # Add title
        story.append(Paragraph("Conversation History Report", title_style))
        story.append(Spacer(1, 20))
        
        # Add conversation details
        story.append(Paragraph("Conversation Information", heading_style))
        story.append(Paragraph(f"<b>Conversation ID:</b> {conversation_id}", normal_style))
        story.append(Paragraph(f"<b>Session ID:</b> {conversation_data['session_id']}", normal_style))
        story.append(Paragraph(f"<b>Timestamp:</b> {conversation_data['timestamp']}", normal_style))
        story.append(Spacer(1, 20))
        
        # Add conversation content
        story.append(Paragraph("Conversation Messages", heading_style))
        
        for i, message in enumerate(conversation_data['content'], 1):
            story.append(Paragraph(f"<b>Message {i}</b>", message_style))
            
            # Add time (datetime only, no timestamp)
            story.append(Paragraph(f"<b>Time:</b> {message.get('datetime', '')}", field_style))
            
            # Add user query
            story.append(Paragraph(f"<b>User Query:</b>", field_style))
            user_query = message.get('user_query', '')
            if len(user_query) > 100:
                # Split long text into paragraphs
                words = user_query.split()
                lines = []
                current_line = ""
                for word in words:
                    if len(current_line + " " + word) <= 80:
                        current_line += " " + word if current_line else word
                    else:
                        lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)
                
                for line in lines:
                    story.append(Paragraph(line, field_style))
            else:
                story.append(Paragraph(user_query, field_style))
            
            # Add response
            story.append(Paragraph(f"<b>Response:</b>", field_style))
            response = message.get('response', '')
            if len(response) > 100:
                # Split long text into paragraphs
                words = response.split()
                lines = []
                current_line = ""
                for word in words:
                    if len(current_line + " " + word) <= 80:
                        current_line += " " + word if current_line else word
                    else:
                        lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)
                
                for line in lines:
                    story.append(Paragraph(line, field_style))
            else:
                story.append(Paragraph(response, field_style))
            
            # Add user emotion
            story.append(Paragraph(f"<b>User Emotion:</b> {message.get('user_emotion', '')}", field_style))
            
            story.append(Spacer(1, 15))
            
            # Add a separator line between messages
            if i < len(conversation_data['content']):
                story.append(Paragraph("<hr/>", normal_style))
                story.append(Spacer(1, 10))
        
        doc.build(story)
        return buffer.getvalue()

def get_session_history(session_id: str):
    """Get or create in-memory chat history for LangChain (separate from file storage)"""
    if session_id not in _sessions:
        _sessions[session_id] = InMemoryChatMessageHistory()
    return _sessions[session_id]