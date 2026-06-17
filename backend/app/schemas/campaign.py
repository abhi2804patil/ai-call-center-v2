import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    script_id: uuid.UUID
    direction: str = "outbound"
    schedule: Optional[dict] = None
    settings: Optional[dict] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    schedule: Optional[dict] = None
    settings: Optional[dict] = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    script_id: uuid.UUID
    name: str
    status: str
    direction: str
    schedule: Optional[dict]
    settings: dict
    phone_list_url: Optional[str]
    total_numbers: int
    called_count: int
    success_count: int
    failed_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignResponse]
    total: int
    page: int
    page_size: int


class PhoneUploadResult(BaseModel):
    total: int
    valid: int
    invalid: int
    duplicates_removed: int
    errors: list[str] = []


class PhoneNumberResponse(BaseModel):
    id: uuid.UUID
    phone_number: str
    customer_data: dict
    status: str
    attempt_count: int
    last_attempted_at: Optional[datetime]

    model_config = {"from_attributes": True}


class CampaignProgress(BaseModel):
    total: int
    called: int
    succeeded: int
    failed: int
    remaining: int
    percent: float
