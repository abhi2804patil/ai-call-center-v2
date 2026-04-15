import asyncio
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.analytics import AnalyticsDaily
from app.models.call_log import CallLog
from app.services.gemini_client import GeminiIntentClassifier
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


async def _generate_summary(call_log_id: str):
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        try:
            result = await db.execute(select(CallLog).where(CallLog.id == call_log_id))
            call_log = result.scalar_one_or_none()
            if not call_log:
                logger.warning(f"Call log not found: {call_log_id}")
                return

            if not call_log.transcript:
                logger.info(f"No transcript for call {call_log_id}, skipping summary")
                return

            gemini = GeminiIntentClassifier()
            summary = await gemini.generate_call_summary(call_log.transcript)

            call_log.ai_summary = summary.get("summary", "")
            call_log.sentiment_score = summary.get("sentiment", 0.0)
            call_log.outcome_tags = summary.get("outcome_tags", [])

            await db.commit()
            logger.info(f"Summary generated for call {call_log_id}")

        except Exception as e:
            logger.error(f"Summary generation failed for {call_log_id}: {e}")
        finally:
            await engine.dispose()


@celery_app.task(name="app.workers.summary_worker.generate_call_summary", bind=True, max_retries=2)
def generate_call_summary(self, call_log_id: str):
    try:
        asyncio.run(_generate_summary(call_log_id))
    except Exception as exc:
        logger.error(f"Summary task error: {exc}")
        self.retry(exc=exc, countdown=60)


async def _aggregate_analytics():
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        try:
            today = date.today()

            results = await db.execute(
                select(
                    CallLog.company_id,
                    CallLog.campaign_id,
                    func.count(CallLog.id).label("total_calls"),
                    func.count(CallLog.id).filter(CallLog.status == "completed").label("successful_calls"),
                    func.count(CallLog.id).filter(CallLog.status == "failed").label("failed_calls"),
                    func.avg(CallLog.duration_seconds).label("avg_duration"),
                    func.sum(func.cast(func.coalesce(CallLog.cost_breakdown["total"].as_float(), 0), None)).label("total_cost"),
                ).where(
                    func.date(CallLog.created_at) == today
                ).group_by(
                    CallLog.company_id, CallLog.campaign_id
                )
            )

            for row in results:
                existing = await db.execute(
                    select(AnalyticsDaily).where(
                        AnalyticsDaily.company_id == row.company_id,
                        AnalyticsDaily.campaign_id == row.campaign_id,
                        AnalyticsDaily.date == today,
                    )
                )
                analytics = existing.scalar_one_or_none()

                if analytics:
                    analytics.total_calls = row.total_calls or 0
                    analytics.successful_calls = row.successful_calls or 0
                    analytics.failed_calls = row.failed_calls or 0
                    analytics.avg_duration_seconds = float(row.avg_duration or 0)
                    analytics.total_cost = float(row.total_cost or 0)
                else:
                    analytics = AnalyticsDaily(
                        company_id=row.company_id,
                        campaign_id=row.campaign_id,
                        date=today,
                        total_calls=row.total_calls or 0,
                        successful_calls=row.successful_calls or 0,
                        failed_calls=row.failed_calls or 0,
                        avg_duration_seconds=float(row.avg_duration or 0),
                        total_cost=float(row.total_cost or 0),
                    )
                    db.add(analytics)

            await db.commit()
            logger.info(f"Daily analytics aggregated for {today}")

        except Exception as e:
            logger.error(f"Analytics aggregation failed: {e}")
        finally:
            await engine.dispose()


@celery_app.task(name="app.workers.summary_worker.aggregate_daily_analytics")
def aggregate_daily_analytics():
    asyncio.run(_aggregate_analytics())
