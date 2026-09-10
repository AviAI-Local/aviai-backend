from sqlalchemy import JSON, Boolean, Column, Float, Integer, String, DateTime, Text, ForeignKey, Enum
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
    personal_characteristics = Column(Text)
    attitude_in_interview = Column(Text)
    rule_interview = Column(Text)
    created_at = Column(DateTime, default=get_vietnam_time)
    times_chosen = Column(Integer, default=0)
    created_by = Column(String, ForeignKey("account.account_id", ondelete="RESTRICT"), nullable=False)
    prompt_id = Column(String, ForeignKey("prompt_template.template_id", ondelete="CASCADE"), nullable=True)
    scenario_text = Column(String)
    category = Column(String)
    # relationship ONE-TO-MANY with other tables
    sessions = relationship("Session", back_populates="scenario", passive_deletes=True)

    # relationship MANY-TO-ONE with other tables
    creator = relationship("Account", back_populates="created_scenarios", foreign_keys=[created_by], passive_deletes=True)
    prompt_template = relationship("PromptTemplate", backref="scenarios", foreign_keys=[prompt_id], passive_deletes=True)
    
    def to_dict(self):
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "personal_characteristics": self.personal_characteristics,
            "attitude_in_interview": self.attitude_in_interview,
            "rule_interview": self.rule_interview,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "times_chosen": self.times_chosen,
            "created_by": self.created_by,
            "prompt_id": self.prompt_id,
            "scenario_text": self.scenario_text,
            "category": self.category
        }
    
class Session(Base):
    __tablename__ = "session"
    session_id = Column(String, primary_key=True, index=True)
    scenario_id = Column(String, ForeignKey("scenario.scenario_id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String, ForeignKey("account.account_id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime, default=get_vietnam_time)
    recording = Column(String, nullable=True)  
    # relationship MANY-TO-ONE with other tables
    scenario = relationship("Scenario", back_populates="sessions", passive_deletes=True) 
    account = relationship("Account", back_populates="sessions", passive_deletes=True)
    # relationship ONE-TO-ONE with other tables
    # conversation_histories = relationship("ConversationHistory", back_populates="session", passive_deletes=True)
    notes = relationship("Note", back_populates="session", passive_deletes=True)

    llm_provider = Column(String, nullable=True)  # "openrouter", "lmstudio"
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


class CIPerformanceEvaluation(Base):
    __tablename__ = "ci_performance_evaluation"
    evaluation_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("account.account_id"), nullable=False)
    conversation_id = Column(String, ForeignKey("conversation_history.conversation_history_id"), nullable=False)
    session_id = Column(String, ForeignKey("session.session_id"), nullable=False)
    
    # Individual weight scores (A1-A5, B6-B8, C9-C10)
    a1_score = Column(Float, nullable=False, default=0.0)  # Open-ended rate
    a2_score = Column(Float, nullable=False, default=0.0)  # Leading rate (inverse)
    a3_score = Column(Float, nullable=False, default=0.0)  # CI phase adherence
    a4_score = Column(Float, nullable=False, default=0.0)  # Pacing & Turn-taking
    a5_score = Column(Float, nullable=False, default=0.0)  # Neutrality & Plain language
    b6_score = Column(Float, nullable=False, default=0.0)  # Trauma-informed empathy
    b7_score = Column(Float, nullable=False, default=0.0)  # Active listening
    b8_score = Column(Float, nullable=False, default=0.0)  # Emotion regulation
    c9_score = Column(Float, nullable=False, default=0.0)  # Structured approach
    c10_score = Column(Float, nullable=False, default=0.0)  # Contamination-safe
    
    # Total score and verdict
    total_score = Column(Float, nullable=False, default=0.0)
    verdict = Column(String, nullable=False)  # PASS, BORDERLINE, FAIL
    
    # CI Phases (boolean flags)
    rapport_safety = Column(Boolean, default=False)
    context_reinstatement = Column(Boolean, default=False)
    free_recall = Column(Boolean, default=False)
    varied_focused_retrieval = Column(Boolean, default=False)
    closure = Column(Boolean, default=False)
    
    # Quantitative metrics
    open_rate = Column(Float, default=0.0)
    leading_rate = Column(Float, default=0.0)
    emotion_regulation = Column(Float, default=0.0)
    
    # Behavioral assessments
    active_listening = Column(String, nullable=False)  # good, fair, poor, absent
    neutral_language = Column(String, nullable=False)  # good, fair, poor
    contamination_risk = Column(String, nullable=False)  # low, medium, high
    pacing_ok = Column(String, nullable=False)  # good, fair, poor
    trauma_informed = Column(String, nullable=False)  # good, fair, poor
    
    # Question classifications (stored as JSON)
    question_classifications = Column(JSON, nullable=True)
    
    # Coaching feedback (stored as JSON)
    coaching_feedback = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=get_vietnam_time)
    updated_at = Column(DateTime, default=get_vietnam_time, onupdate=get_vietnam_time)
    
    # Relationships
    user = relationship("Account")
    conversation = relationship("ConversationHistory")
    session = relationship("Session")
    
    def to_dict(self):
        return {
            "evaluation_id": self.evaluation_id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "a1_score": self.a1_score,
            "a2_score": self.a2_score,
            "a3_score": self.a3_score,
            "a4_score": self.a4_score,
            "a5_score": self.a5_score,
            "b6_score": self.b6_score,
            "b7_score": self.b7_score,
            "b8_score": self.b8_score,
            "c9_score": self.c9_score,
            "c10_score": self.c10_score,
            "total_score": self.total_score,
            "verdict": self.verdict,
            "rapport_safety": self.rapport_safety,
            "context_reinstatement": self.context_reinstatement,
            "free_recall": self.free_recall,
            "varied_focused_retrieval": self.varied_focused_retrieval,
            "closure": self.closure,
            "open_rate": self.open_rate,
            "leading_rate": self.leading_rate,
            "emotion_regulation": self.emotion_regulation,
            "active_listening": self.active_listening,
            "neutral_language": self.neutral_language,
            "contamination_risk": self.contamination_risk,
            "pacing_ok": self.pacing_ok,
            "trauma_informed": self.trauma_informed,
            "question_classifications": self.question_classifications,
            "coaching_feedback": self.coaching_feedback,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class PromptTemplate(Base):
    __tablename__ = "prompt_template"

    template_id = Column(String, primary_key=True, index=True)
    template_name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=True, default="general")  # "cognitive_interview", "general", "specific"
    content = Column(Text, nullable=False)

    # Audit fields
    created_by = Column(String, ForeignKey("account.account_id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime, default=get_vietnam_time)
    updated_at = Column(DateTime, default=get_vietnam_time, onupdate=get_vietnam_time)

    # Relationships
    # Note: scenarios relationship is auto-created via backref in Scenario model
    creator = relationship("Account", backref="created_prompts", foreign_keys=[created_by])

    def to_dict(self):
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "category": self.category,
            "content": self.content,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }    