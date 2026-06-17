import io
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.call_log import CallLog
from app.models.campaign import Campaign
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsOverview,
    DailyTrend,
    DashboardResponse,
    TopCampaign,
)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    campaign_id: Optional[uuid.UUID] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    base_query = select(CallLog).where(
        CallLog.company_id == user.company_id,
        func.date(CallLog.created_at) >= start_date,
        func.date(CallLog.created_at) <= end_date,
    )
    if campaign_id:
        base_query = base_query.where(CallLog.campaign_id == campaign_id)

    # Overview
    overview_result = await db.execute(
        select(
            func.count(CallLog.id).label("total"),
            func.count(CallLog.id).filter(CallLog.status == "completed").label("successful"),
            func.count(CallLog.id).filter(CallLog.status == "failed").label("failed"),
            func.avg(CallLog.duration_seconds).label("avg_duration"),
        ).where(
            CallLog.company_id == user.company_id,
            func.date(CallLog.created_at) >= start_date,
            func.date(CallLog.created_at) <= end_date,
        )
    )
    row = overview_result.one()
    total = row.total or 0
    successful = row.successful or 0
    failed = row.failed or 0
    avg_dur = float(row.avg_duration or 0)
    success_rate = (successful / total * 100) if total > 0 else 0

    # Language breakdown
    lang_result = await db.execute(
        select(
            CallLog.language_detected,
            func.count(CallLog.id),
        ).where(
            CallLog.company_id == user.company_id,
            func.date(CallLog.created_at) >= start_date,
            func.date(CallLog.created_at) <= end_date,
            CallLog.language_detected.isnot(None),
        ).group_by(CallLog.language_detected)
    )
    language_breakdown = {r[0]: r[1] for r in lang_result.all()}

    overview = AnalyticsOverview(
        total_calls=total,
        successful_calls=successful,
        failed_calls=failed,
        avg_duration=round(avg_dur, 1),
        total_cost=0.0,
        success_rate=round(success_rate, 1),
        language_breakdown=language_breakdown,
    )

    # Trends
    trends_result = await db.execute(
        select(
            func.date(CallLog.created_at).label("day"),
            func.count(CallLog.id).label("total"),
            func.count(CallLog.id).filter(CallLog.status == "completed").label("successful"),
            func.count(CallLog.id).filter(CallLog.status == "failed").label("failed"),
        ).where(
            CallLog.company_id == user.company_id,
            func.date(CallLog.created_at) >= start_date,
            func.date(CallLog.created_at) <= end_date,
        ).group_by(func.date(CallLog.created_at)).order_by(func.date(CallLog.created_at))
    )
    trends = [
        DailyTrend(
            date=r.day,
            total_calls=r.total or 0,
            successful_calls=r.successful or 0,
            failed_calls=r.failed or 0,
            total_cost=0.0,
        )
        for r in trends_result.all()
    ]

    # Top campaigns
    top_result = await db.execute(
        select(
            CallLog.campaign_id,
            func.count(CallLog.id).label("total"),
            func.count(CallLog.id).filter(CallLog.status == "completed").label("successful"),
        ).where(
            CallLog.company_id == user.company_id,
            func.date(CallLog.created_at) >= start_date,
            func.date(CallLog.created_at) <= end_date,
            CallLog.campaign_id.isnot(None),
        ).group_by(CallLog.campaign_id).order_by(func.count(CallLog.id).desc()).limit(10)
    )

    top_campaigns = []
    for r in top_result.all():
        campaign_result = await db.execute(select(Campaign.name).where(Campaign.id == r.campaign_id))
        name_row = campaign_result.first()
        campaign_name = name_row[0] if name_row else "Unknown"
        sr = (r.successful / r.total * 100) if r.total > 0 else 0
        top_campaigns.append(
            TopCampaign(
                campaign_id=str(r.campaign_id),
                name=campaign_name,
                total_calls=r.total,
                success_rate=round(sr, 1),
            )
        )

    return DashboardResponse(
        overview=overview,
        trends=trends,
        top_campaigns=top_campaigns,
    )


@router.get("/campaigns/{campaign_id}")
async def get_campaign_analytics(
    campaign_id: uuid.UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    result = await db.execute(
        select(
            func.count(CallLog.id).label("total"),
            func.count(CallLog.id).filter(CallLog.status == "completed").label("successful"),
            func.count(CallLog.id).filter(CallLog.status == "failed").label("failed"),
            func.avg(CallLog.duration_seconds).label("avg_duration"),
        ).where(
            CallLog.company_id == user.company_id,
            CallLog.campaign_id == campaign_id,
            func.date(CallLog.created_at) >= start_date,
            func.date(CallLog.created_at) <= end_date,
        )
    )
    row = result.one()

    return {
        "campaign_id": str(campaign_id),
        "total_calls": row.total or 0,
        "successful_calls": row.successful or 0,
        "failed_calls": row.failed or 0,
        "avg_duration": round(float(row.avg_duration or 0), 1),
        "success_rate": round((row.successful / row.total * 100) if row.total else 0, 1),
    }


@router.get("/export")
async def export_analytics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    result = await db.execute(
        select(CallLog).where(
            CallLog.company_id == user.company_id,
            func.date(CallLog.created_at) >= start_date,
            func.date(CallLog.created_at) <= end_date,
        ).order_by(CallLog.created_at.desc())
    )
    calls = result.scalars().all()

    csv_content = "id,phone_number,direction,status,language,duration_seconds,started_at,ended_at,sentiment_score\n"
    for c in calls:
        csv_content += (
            f"{c.id},{c.phone_number},{c.direction},{c.status},"
            f"{c.language_detected or ''},{c.duration_seconds},"
            f"{c.started_at or ''},{c.ended_at or ''},{c.sentiment_score or ''}\n"
        )

    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=analytics_{start_date}_{end_date}.csv"},
    )
