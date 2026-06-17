import uuid
from datetime import datetime
from typing import Optional

import boto3
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.call_log import CallLog
from app.models.user import User
from app.schemas.call import CallListResponse, CallLogResponse

router = APIRouter()
settings = get_settings()


@router.get("", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    campaign_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    language: Optional[str] = None,
    phone: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(CallLog).where(CallLog.company_id == user.company_id)

    if campaign_id:
        query = query.where(CallLog.campaign_id == campaign_id)
    if status_filter:
        query = query.where(CallLog.status == status_filter)
    if language:
        query = query.where(CallLog.language_detected == language)
    if phone:
        query = query.where(CallLog.phone_number.ilike(f"%{phone}%"))
    if start_date:
        query = query.where(CallLog.created_at >= start_date)
    if end_date:
        query = query.where(CallLog.created_at <= end_date)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(CallLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    calls = result.scalars().all()

    return CallListResponse(
        calls=[CallLogResponse.model_validate(c) for c in calls],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/live")
async def list_live_calls(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CallLog).where(
            CallLog.company_id == user.company_id,
            CallLog.status.in_(["in-progress", "ringing", "connected"]),
        )
    )
    calls = result.scalars().all()
    return {
        "live_calls": [
            {
                "id": str(c.id),
                "phone_number": c.phone_number,
                "status": c.status,
                "duration": c.duration_seconds,
                "language_used": c.language_detected,
                "current_node": c.transcript[-1].get("node_key") if c.transcript else None,
                "transcript": c.transcript[-10:] if c.transcript else [],
            }
            for c in calls
        ]
    }


@router.get("/{call_id}", response_model=CallLogResponse)
async def get_call(
    call_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CallLog).where(CallLog.id == call_id, CallLog.company_id == user.company_id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return CallLogResponse.model_validate(call)


@router.get("/{call_id}/recording")
async def get_recording(
    call_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CallLog).where(CallLog.id == call_id, CallLog.company_id == user.company_id)
    )
    call = result.scalar_one_or_none()
    if not call or not call.recording_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

    key = call.recording_url.split(f"{settings.AWS_S3_BUCKET}/")[-1] if settings.AWS_S3_BUCKET in (call.recording_url or "") else ""
    if key:
        presigned = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET, "Key": key},
            ExpiresIn=3600,
        )
        return RedirectResponse(url=presigned)

    return RedirectResponse(url=call.recording_url)


@router.post("/{call_id}/takeover")
async def takeover_call(
    call_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CallLog).where(
            CallLog.id == call_id,
            CallLog.company_id == user.company_id,
            CallLog.status.in_(["in-progress", "connected"]),
        )
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active call not found",
        )

    from app.services.telephony_client import TelephonyClient
    telephony = TelephonyClient()
    escalation_number = "+919999999999"
    try:
        await telephony.transfer_call(str(call.id), escalation_number)
        call.status = "transferred"
        await db.flush()
        return {"message": "Call transferred to human agent", "call_id": str(call.id)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer failed: {str(e)}",
        )
