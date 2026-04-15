import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_agent_or_admin
from app.models.campaign import Campaign
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignListResponse,
    CampaignProgress,
    CampaignResponse,
    CampaignUpdate,
    PhoneNumberResponse,
    PhoneUploadResult,
)
from app.services.campaign_manager import CampaignManager

router = APIRouter()


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Campaign).where(Campaign.company_id == user.company_id)
    if status_filter:
        query = query.where(Campaign.status == status_filter)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Campaign.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    campaigns = result.scalars().all()

    return CampaignListResponse(
        campaigns=[CampaignResponse.model_validate(c) for c in campaigns],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == user.company_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    user: User = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    manager = CampaignManager()
    campaign = await manager.create_campaign(db, user.company_id, data)
    return CampaignResponse.model_validate(campaign)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == user.company_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if campaign.status not in ("draft", "paused"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update draft or paused campaigns",
        )

    if data.name is not None:
        campaign.name = data.name
    if data.schedule is not None:
        campaign.schedule = data.schedule
    if data.settings is not None:
        campaign.settings = data.settings

    await db.flush()
    return CampaignResponse.model_validate(campaign)


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == user.company_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    campaign.status = "cancelled"
    await db.flush()
    return {"message": "Campaign deleted"}


@router.post("/{campaign_id}/upload-phones", response_model=PhoneUploadResult)
async def upload_phone_list(
    campaign_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted",
        )

    content = await file.read()
    manager = CampaignManager()
    return await manager.upload_phone_list(db, campaign_id, user.company_id, content)


@router.post("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    manager = CampaignManager()
    campaign = await manager.start_campaign(db, campaign_id, user.company_id)
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    manager = CampaignManager()
    campaign = await manager.pause_campaign(db, campaign_id, user.company_id)
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    manager = CampaignManager()
    campaign = await manager.resume_campaign(db, campaign_id, user.company_id)
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/stop", response_model=CampaignResponse)
async def stop_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    manager = CampaignManager()
    campaign = await manager.stop_campaign(db, campaign_id, user.company_id)
    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}/progress", response_model=CampaignProgress)
async def get_progress(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    manager = CampaignManager()
    return await manager.get_progress(db, campaign_id)


@router.get("/{campaign_id}/phone-numbers")
async def list_phone_numbers(
    campaign_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign_result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == user.company_id)
    )
    if not campaign_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    query = select(PhoneNumber).where(PhoneNumber.campaign_id == campaign_id)
    if status_filter:
        query = query.where(PhoneNumber.status == status_filter)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(PhoneNumber.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    numbers = result.scalars().all()

    return {
        "phone_numbers": [PhoneNumberResponse.model_validate(n) for n in numbers],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
