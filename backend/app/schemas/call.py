import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TranscriptEntry(BaseModel):
    role: str
    text: str
    node_key: Optional[str] = None
    timestamp: Optional[str] = None
    intent: Optional[str] = None
    confidence: Optional[float] = None


class CallLogResponse(BaseModel):
    id: uuid.UUID
    campaign_id: Optional[uuid.UUID]
    company_id: uuid.UUID
    phone_number: str
    direction: str
    status: str
    language_detected: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: int
    recording_url: Optional[str]
    transcript: list
    ai_summary: Optional[str]
    sentiment_score: Optional[float]
    outcome_tags: list
    cost_breakdown: dict
    metadata_: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class CallListResponse(BaseModel):
    calls: list[CallLogResponse]
    total: int
    page: int
    page_size: int


class LiveCallResponse(BaseModel):
    id: str
    phone_number: str
    status: str
    duration: int
    language_used: Optional[str]
    current_node: Optional[str]
    transcript: list[TranscriptEntry] = []
