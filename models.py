"""saving CRM tickets in mongo and validate bad data before storing"""

from datetime import datetime, timezone
from typing import List, Literal, Optional
 
from pydantic import BaseModel, Field
 
LeadTemperature = Literal["hot", "warm", "cold"]
LeadStatus = Literal["new", "contacted", "converted", "lost"]
 
 
class CRMLeadTicket(BaseModel):
    """One captured sales lead, written to MongoDB by capture_and_save_crm_lead."""
 
    name: str = Field(..., description="Full name as stated by the user")
    contact: str = Field(..., description="WhatsApp number with country code or email address")
    city_country: str = Field(default="غير محدد", description="User's city and country")
    language_dialect: str = Field(default="العربية", description="Detected language and dialect")
 
    products_interested: List[str] = Field(
        default_factory=list,
        description="Diplomas or courses the user showed interest in",
    )
    goal: str = Field(default="", description="Career goal or learning motivation")
    current_level: str = Field(
        default="مبتدئ",
        description="Technical level — free text, e.g. 'مبتدئ — خبرة بسيطة في الشبكات'",
    )
 
    lead_temperature: LeadTemperature = Field(
        ..., description="hot (ready to enroll) / warm (considering) / cold (browsing)"
    )
    buying_signals: List[str] = Field(
        default_factory=list, description="Signals observed, e.g. 'asked about price'"
    )
    objections: List[str] = Field(
        default_factory=list, description="Concerns raised, e.g. cost, time commitment"
    )
 
    conversation_summary: str = Field(..., description="2-3 sentence Arabic summary")
    recommended_action: str = Field(..., description="Next action for the sales rep")
 
    status: LeadStatus = Field(default="new", description="CRM lifecycle status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
 
    class Config:
        json_encoders = {datetime: lambda dt: dt.isoformat()}
 
 
class ConversationTurn(BaseModel):
    """One chat turn, written to MongoDB by ConversationDB.save_turn."""
 
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    user_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))