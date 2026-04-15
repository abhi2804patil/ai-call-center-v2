import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.call_log import CallLog
from app.services.telephony_client import TelephonyClient

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def _verify_exotel_signature(payload: dict, signature: str | None) -> bool:
    """Verify Exotel webhook signature using API token as HMAC key."""
    if not settings.EXOTEL_API_TOKEN:
        logger.warning("EXOTEL_API_TOKEN not set, skipping webhook signature verification")
        return True
    if not signature:
        return False
    sorted_values = "".join(str(payload.get(k, "")) for k in sorted(payload.keys()))
    expected = hmac.new(
        settings.EXOTEL_API_TOKEN.encode(),
        sorted_values.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/exotel/status")
async def exotel_status_webhook(request: Request):
    try:
        body = await request.form()
        payload = dict(body)

        signature = request.headers.get("X-Exotel-Signature")
        if not _verify_exotel_signature(payload, signature):
            logger.warning(f"Invalid webhook signature from {request.client.host}")
            raise HTTPException(status_code=403, detail="Invalid signature")

        telephony = TelephonyClient()
        normalized = telephony.handle_webhook(payload)

        call_sid = normalized["call_sid"]
        call_status = normalized["status"]

        logger.info(f"Exotel webhook: call_sid={call_sid}, status={call_status}")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CallLog).where(CallLog.exotel_call_sid == call_sid)
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return Response(status_code=200)
