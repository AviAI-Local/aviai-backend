from sqlalchemy import JSON, Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database.config import Base
import enum
import pytz
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

def get_vietnam_timezone():
    """Get Vietnam timezone object."""
    return pytz.timezone('Asia/Ho_Chi_Minh')

def get_vietnam_time():
    """Get current time in Vietnam timezone."""
    vietnam_tz = get_vietnam_timezone()
    return datetime.now(vietnam_tz)

class RoleEnum(enum.Enum):
    ADMIN = "admin"
    STUDENT = "student"

class GenderEnum(enum.Enum):
    MALE = "male"
    FEMALE = "female"

class Account(Base):
    __tablename__ = "account"
    account_id = Column(String, primary_key=True, index=True)
    user_name = Column(String, nullable=True)  
    avatar = Column(String, nullable=True)     
    major = Column(String, nullable=True)      
    account_name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    # relationship ONE-TO-MANY with other tables
    sessions = relationship("Session", back_populates="account", passive_deletes=True)
    notes = relationship("Note", back_populates="account", passive_deletes=True)
    created_scenarios = relationship("Scenario", back_populates="creator", foreign_keys="Scenario.created_by", passive_deletes=True)

    def to_dict(self):
        return {
            "account_id": self.account_id,
            "user_name": self.user_name,      
            "avatar": self.avatar,            
            "major": self.major,              
            "account_name": self.account_name,
            "password": self.password,
            "role": self.role.value if self.role else None
        }

class Scenario(Base):
    __tablename__ = "scenario"
    scenario_id = Column(String, primary_key=True, index=True)
    scenario_name = Column(String)
    scenario_summary = Column(Text)
    personal_characteristics = Column(Text)
    attitude_in_interview = Column(Text)
    rule_interview = Column(Text)
    character_name = Column(String)
    character_gender = Column(Enum(GenderEnum))
    created_at = Column(DateTime, default=get_vietnam_time)
    times_chosen = Column(Integer, default=0)
    created_by = Column(String, ForeignKey("account.account_id", ondelete="RESTRICT"), nullable=False)
    industry = Column(String)
    scenario_text = Column(String)  
    # relationship ONE-TO-MANY with other tables
    sessions = relationship("Session", back_populates="scenario", passive_deletes=True)

    # relationship MANY-TO-ONE with other tables
    creator = relationship("Account", back_populates="created_scenarios", foreign_keys=[created_by], passive_deletes=True)
    
    def to_dict(self):
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "scenario_summary": self.scenario_summary,
            "personal_characteristics": self.personal_characteristics,
            "attitude_in_interview": self.attitude_in_interview,
            "rule_interview": self.rule_interview,
            "character_name": self.character_name,
            "character_gender": self.character_gender.value if self.character_gender else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "times_chosen": self.times_chosen,
            "created_by": self.created_by,
            "industry": self.industry,
            "scenario_text": self.scenario_text  
        }
    
class Session(Base):
    __tablename__ = "session"
    session_id = Column(String, primary_key=True, index=True)
    scenario_id = Column(String, ForeignKey("scenario.scenario_id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String, ForeignKey("account.account_id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime, default=get_vietnam_time)
    recording = Column(String)  
    # relationship MANY-TO-ONE with other tables
    scenario = relationship("Scenario", back_populates="sessions", passive_deletes=True) 
    account = relationship("Account", back_populates="sessions", passive_deletes=True)
    # relationship ONE-TO-ONE with other tables
    # conversation_histories = relationship("ConversationHistory", back_populates="session", passive_deletes=True)
    notes = relationship("Note", back_populates="session", passive_deletes=True)
    
    llm_provider = Column(String, nullable=True)  # "ollama", "lmstudio"
    model = Column(String, nullable=True)         # "llama3", "gpt-4"

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "scenario_id": self.scenario_id,
            "account_id": self.account_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "recording": self.recording
        }
    
class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    conversation_history_id = Column(String, primary_key=True, index=True)
    session_id = Column(String)
    # session_id = Column(String, primary_key=True, index=True)
    # session_id = Column(String, ForeignKey("session.session_id", ondelete="CASCADE"), nullable=False)
    content = Column(JSON)  # Stores a list of message dicts in JSON format
    timestamp = Column(DateTime, default=get_vietnam_time)
    # relationship MANY-TO-ONE with other tables
    # session = relationship("Session", back_populates="conversation_histories", passive_deletes=True)
    
    def to_dict(self):
        return {
            "conversation_history_id": self.conversation_history_id,
            "session_id": self.session_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
    
class Note(Base):
    __tablename__ = "note"
    note_id = Column(String, primary_key=True, index=True)  
    session_id = Column(String, ForeignKey("session.session_id", ondelete="CASCADE"), nullable=True)    
    account_id = Column(String, ForeignKey("account.account_id", ondelete="RESTRICT"), nullable=False)
    title = Column(String)
    note_content = Column(JSON)  
    timestamp = Column(DateTime, default=get_vietnam_time)
    # relationship MANY-TO-ONE with other tables
    session = relationship("Session", back_populates="notes", passive_deletes=True)       
    account = relationship("Account", back_populates="notes", passive_deletes=True)
    
    def to_dict(self):
        return {
            "note_id": self.note_id,
            "session_id": self.session_id,
            "account_id": self.account_id,
            "title": self.title,
            "note_content": self.note_content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
class ConversationAnalysis(Base):
    __tablename__ = "conversation_analysis"

    analysis_id = Column(String, primary_key=True, index=True)

    conversation_history_id = Column(
        String,
        ForeignKey(
            "conversation_history.conversation_history_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )

    summary = Column(Text, nullable=False)
    analysis = Column(JSONB, nullable=False)

    pdf_base64 = Column(Text, nullable=False)
    filename = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # relationship
    conversation_history = relationship(
        "ConversationHistory",
        passive_deletes=True,
    )

    def to_dict(self):
        return {
            "analysis_id": self.analysis_id,
            "conversation_history_id": self.conversation_history_id,
            "summary": self.summary,
            "analysis": self.analysis,
            "filename": self.filename,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
