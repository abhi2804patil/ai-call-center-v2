import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScriptNode(BaseModel):
    text: dict[str, str]
    dynamic_slots: list[str] = []
    next_action: str = "listen"


class ScriptContent(BaseModel):
    persona: str
    default_language: str = "hi"
    supported_languages: list[str] = ["hi", "en"]
    voice_id: str = "meera"
    nodes: dict[str, ScriptNode]
    intent_map: dict[str, list[str]]
    escalation: dict = {}
    guardrails: list[str] = []


class ScriptCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    content: ScriptContent


class ScriptUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    content: Optional[ScriptContent] = None
    is_active: Optional[bool] = None


class ScriptResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    description: Optional[str]
    version: int
    content: dict
    audio_status: str
    is_active: bool
    audio_file_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScriptAudioResponse(BaseModel):
    id: uuid.UUID
    node_key: str
    language_code: str
    voice_id: str
    text_content: str
    audio_url: str
    audio_duration_ms: int
    status: str

    model_config = {"from_attributes": True}


class ScriptListResponse(BaseModel):
    scripts: list[ScriptResponse]
    total: int
    page: int
    page_size: int
