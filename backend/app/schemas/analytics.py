from datetime import date
from typing import Optional

from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_duration: float = 0.0
    total_cost: float = 0.0
    success_rate: float = 0.0
    language_breakdown: dict = {}


class DailyTrend(BaseModel):
    date: date
    total_calls: int
    successful_calls: int
    failed_calls: int
    total_cost: float


class TopCampaign(BaseModel):
    campaign_id: str
    name: str
    total_calls: int
    success_rate: float


class DashboardResponse(BaseModel):
    overview: AnalyticsOverview
    trends: list[DailyTrend] = []
    top_campaigns: list[TopCampaign] = []
