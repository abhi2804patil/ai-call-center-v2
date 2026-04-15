import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.call_log import CallLog
from app.models.campaign import Campaign
from app.models.phone_number import PhoneNumber
from app.models.script import Script
from app.services.telephony_client import TelephonyClient
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


async def _process_campaign(campaign_id_str: str):
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        try:
            campaign_id = uuid.UUID(campaign_id_str)
            result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
            campaign = result.scalar_one_or_none()
            if not campaign or campaign.status != "active":
                logger.info(f"Campaign {campaign_id_str} not active, skipping")
                return

            concurrent_limit = campaign.settings.get("concurrent_limit", 10)
            max_retries = campaign.settings.get("max_retries", 3)

            pending_result = await db.execute(
                select(PhoneNumber).where(
                    PhoneNumber.campaign_id == campaign_id,
                    PhoneNumber.status == "pending",
                ).limit(concurrent_limit)
            )
            pending_numbers = pending_result.scalars().all()

            if not pending_numbers:
                campaign.status = "completed"
                campaign.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"Campaign {campaign_id_str} completed")
                return

            telephony = TelephonyClient()
            callback_url = f"http://backend:8000/api/v1/webhooks/exotel/status"

            for phone_record in pending_numbers:
                refresh_result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
                refreshed = refresh_result.scalar_one_or_none()
                if not refreshed or refreshed.status != "active":
                    logger.info(f"Campaign {campaign_id_str} no longer active, stopping")
                    break

                try:
                    phone_record.status = "calling"
                    phone_record.attempt_count += 1
                    phone_record.last_attempted_at = datetime.now(timezone.utc)
                    await db.flush()

                    call_log = CallLog(
                        campaign_id=campaign_id,
                        company_id=campaign.company_id,
                        phone_number=phone_record.phone_number,
                        direction="outbound",
                        status="initiated",
                        started_at=datetime.now(timezone.utc),
                        metadata_=phone_record.customer_data,
                    )
                    db.add(call_log)
                    await db.flush()

                    call_result = await telephony.make_call(
                        from_number="+911234567890",
                        to_number=phone_record.phone_number,
                        callback_url=callback_url,
                    )

                    phone_record.status = "called"
                    campaign.called_count += 1
                    await db.flush()

                    logger.info(
                        f"Call initiated for {phone_record.phone_number} "
                        f"in campaign {campaign_id_str}"
                    )

                except Exception as e:
                    logger.error(f"Failed to call {phone_record.phone_number}: {e}")
                    phone_record.status = "failed" if phone_record.attempt_count >= max_retries else "pending"
                    if phone_record.status == "failed":
                        campaign.failed_count += 1
                    await db.flush()

            await db.commit()
            await telephony.close()

        except Exception as e:
            logger.error(f"Campaign processing error: {e}")
        finally:
            await engine.dispose()


@celery_app.task(name="app.workers.call_worker.process_campaign_calls", bind=True, max_retries=1)
def process_campaign_calls(self, campaign_id: str):
    try:
        asyncio.run(_process_campaign(campaign_id))
    except Exception as exc:
        logger.error(f"Campaign task error: {exc}")
        self.retry(exc=exc, countdown=60)


async def _initiate_single(campaign_id_str: str, phone_number_id_str: str):
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        try:
            phone_id = uuid.UUID(phone_number_id_str)
            result = await db.execute(select(PhoneNumber).where(PhoneNumber.id == phone_id))
            phone_record = result.scalar_one_or_none()
            if not phone_record:
                return

            telephony = TelephonyClient()
            callback_url = f"http://backend:8000/api/v1/webhooks/exotel/status"

            call_result = await telephony.make_call(
                from_number="+911234567890",
                to_number=phone_record.phone_number,
                callback_url=callback_url,
            )

            phone_record.status = "called"
            phone_record.attempt_count += 1
            phone_record.last_attempted_at = datetime.now(timezone.utc)
            await db.commit()

            await telephony.close()

        except Exception as e:
            logger.error(f"Single call initiation error: {e}")
        finally:
            await engine.dispose()


@celery_app.task(name="app.workers.call_worker.initiate_single_call")
def initiate_single_call(campaign_id: str, phone_number_id: str):
    asyncio.run(_initiate_single(campaign_id, phone_number_id))
