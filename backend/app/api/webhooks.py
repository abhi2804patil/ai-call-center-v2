import hashlib
import hmac
import logging
import uuid

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
    if settings.APP_ENV == "development":
        logger.debug("Development mode: skipping webhook signature verification")
        return True
    if not settings.EXOTEL_API_TOKEN:
        logger.warning("EXOTEL_API_TOKEN not set, skipping webhook signature verification")
        return True
    if not signature:
        return False
    sorted_values = "".join(str(payload.get(k, "")) for k in sorted(payload.keys()))
    expected = hmac.HMAC(
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


def _build_exoml(*verbs: str) -> Response:
    """Build an ExoML XML response."""
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n' + "\n".join(verbs) + "\n</Response>"
    return Response(content=body, media_type="application/xml")


@router.post("/exotel/answer")
@router.get("/exotel/answer")
async def exotel_answer_webhook(request: Request):
    """Fallback answer endpoint.

    The Voicebot applet in App Bazar handles the actual call flow by
    connecting directly to our WebSocket. This endpoint is only hit
    if the call flow falls through to a Passthru/Connect applet.
    """
    params = dict(request.query_params)
    if request.method == "POST":
        body = await request.form()
        params.update(dict(body))

    call_sid = params.get("CallSid", "")
    logger.info(f"Exotel answer webhook (fallback): call_sid={call_sid}")

    # Return a simple hangup — the Voicebot applet should handle calls,
    # not this endpoint
    return _build_exoml('  <Hangup/>')
