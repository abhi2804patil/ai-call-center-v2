import logging

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.call_log import CallLog
from app.services.telephony_client import TelephonyClient

logger = logging.getLogger(__name__)
router = APIRouter()

telephony = TelephonyClient()


@router.post("/exotel/status")
async def exotel_status_webhook(request: Request):
    try:
        body = await request.form()
        payload = dict(body)
        normalized = telephony.handle_webhook(payload)

        call_sid = normalized["call_sid"]
        call_status = normalized["status"]

        logger.info(f"Exotel webhook: call_sid={call_sid}, status={call_status}")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CallLog).where(CallLog.id == call_sid)
            )
            call_log = result.scalar_one_or_none()

            if call_log:
                if call_status in ("completed", "failed", "busy", "no-answer"):
                    call_log.status = call_status
                    call_log.duration_seconds = normalized.get("duration", 0)
                    if normalized.get("recording_url"):
                        call_log.recording_url = normalized["recording_url"]
                elif call_status == "in-progress":
                    call_log.status = "in-progress"

                await db.commit()

            if call_status == "in-progress" and call_log:
                logger.info(f"Call in-progress: {call_sid}, starting orchestrator")

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return Response(status_code=200)
