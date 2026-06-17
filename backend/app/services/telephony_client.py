import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class TelephonyError(Exception):
    pass


class TelephonyClient:
    def __init__(self):
        settings = get_settings()
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        self.client = httpx.AsyncClient(
            timeout=30.0,
            auth=(self.account_sid, self.auth_token),
        )

    async def make_call(
        self,
        from_number: str,
        to_number: str,
        callback_url: str,
    ) -> dict:
        """Initiate an outbound call via Twilio.

        Uses TwiML <Connect><Stream> to establish a bidirectional
        WebSocket for real-time audio streaming to our voicebot.
        """
        url = f"{self.base_url}/Calls.json"
        settings = get_settings()
        ws_url = settings.SERVER_BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

        # TwiML that connects the call to our WebSocket for bidirectional streaming
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            "<Connect>"
            f'<Stream url="{ws_url}/ws/voicebot" />'
            "</Connect>"
            "</Response>"
        )

        data = {
            "From": from_number,
            "To": to_number,
            "Twiml": twiml,
            "StatusCallback": callback_url,
            "StatusCallbackEvent": "initiated ringing answered completed",
        }

        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            result = response.json()
            call_sid = result.get("sid", "")
            status = result.get("status", "queued")
            logger.info(f"Call initiated: {call_sid} to {to_number}")
            return {"call_sid": call_sid, "status": status}
        except httpx.HTTPError as e:
            logger.error(f"Failed to make call to {to_number}: {e}")
            raise TelephonyError(f"Failed to initiate call: {e}")

    async def get_call_status(self, call_sid: str) -> dict:
        url = f"{self.base_url}/Calls/{call_sid}.json"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            result = response.json()
            return {
                "status": result.get("status", "unknown"),
                "duration": int(result.get("duration") or 0),
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to get call status for {call_sid}: {e}")
            raise TelephonyError(f"Failed to get call status: {e}")

    async def end_call(self, call_sid: str) -> dict:
        url = f"{self.base_url}/Calls/{call_sid}.json"
        data = {"Status": "completed"}
        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            logger.info(f"Call {call_sid} ended")
            return {"status": "completed"}
        except httpx.HTTPError as e:
            logger.error(f"Failed to end call {call_sid}: {e}")
            raise TelephonyError(f"Failed to end call: {e}")

    def handle_webhook(self, payload: dict) -> dict:
        return {
            "call_sid": payload.get("CallSid", ""),
            "status": payload.get("CallStatus", "").lower(),
            "direction": payload.get("Direction", "outbound-api").lower(),
            "from_number": payload.get("From", ""),
            "to_number": payload.get("To", ""),
            "duration": int(payload.get("CallDuration") or payload.get("Duration") or 0),
            "recording_url": payload.get("RecordingUrl", ""),
        }

    async def close(self):
        await self.client.aclose()
