import base64
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class TelephonyError(Exception):
    pass


class TelephonyClient:
    def __init__(self):
        settings = get_settings()
        self.sid = settings.EXOTEL_SID
        self.api_key = settings.EXOTEL_API_KEY
        self.api_token = settings.EXOTEL_API_TOKEN
        self.subdomain = settings.EXOTEL_SUBDOMAIN
        self.base_url = f"https://{self.subdomain}.exotel.com/v1/Accounts/{self.sid}"
        auth_str = f"{self.api_key}:{self.api_token}"
        self.auth_header = base64.b64encode(auth_str.encode()).decode()
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Basic {self.auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

    async def make_call(
        self,
        from_number: str,
        to_number: str,
        callback_url: str,
    ) -> dict:
        url = f"{self.base_url}/Calls/connect.json"
        settings = get_settings()
        # Use Exotel App Bazar flow URL — the app contains the Voicebot applet
        # which connects directly to our WebSocket for bidirectional audio
        app_url = f"http://my.exotel.com/{self.sid}/exoml/start_voice/{settings.EXOTEL_APP_ID}"
        data = {
            "From": to_number,
            "CallerId": from_number,
            "Url": app_url,
            "StatusCallback": callback_url,
        }

        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            result = response.json()
            call_data = result.get("Call", {})
            call_sid = call_data.get("Sid", "")
            status = call_data.get("Status", "queued")
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
            call_data = result.get("Call", {})
            return {
                "status": call_data.get("Status", "unknown"),
                "duration": int(call_data.get("Duration", 0)),
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to get call status for {call_sid}: {e}")
            raise TelephonyError(f"Failed to get call status: {e}")

    async def play_audio(self, call_sid: str, audio_url: str) -> dict:
        url = f"{self.base_url}/Calls/{call_sid}/play.json"
        data = {"AudioUrl": audio_url}

        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            logger.info(f"Playing audio for call {call_sid}: {audio_url[:80]}")
            return {"status": "playing"}
        except httpx.HTTPError as e:
            logger.error(f"Failed to play audio for call {call_sid}: {e}")
            raise TelephonyError(f"Failed to play audio: {e}")

    async def play_audio_bytes(self, call_sid: str, audio_bytes: bytes) -> dict:
        url = f"{self.base_url}/Calls/{call_sid}/play.json"
        audio_b64 = base64.b64encode(audio_bytes).decode()
        data = {"AudioData": audio_b64, "AudioFormat": "wav"}

        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            logger.info(f"Playing audio bytes for call {call_sid}")
            return {"status": "playing"}
        except httpx.HTTPError as e:
            logger.error(f"Failed to play audio bytes for call {call_sid}: {e}")
            raise TelephonyError(f"Failed to play audio bytes: {e}")

    async def transfer_call(self, call_sid: str, transfer_to: str) -> dict:
        url = f"{self.base_url}/Calls/{call_sid}/transfer.json"
        data = {"To": transfer_to}

        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            logger.info(f"Call {call_sid} transferred to {transfer_to}")
            return {"status": "transferred"}
        except httpx.HTTPError as e:
            logger.error(f"Failed to transfer call {call_sid}: {e}")
            raise TelephonyError(f"Failed to transfer call: {e}")

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
            "status": payload.get("Status", "").lower(),
            "direction": payload.get("Direction", "outbound").lower(),
            "from_number": payload.get("From", ""),
            "to_number": payload.get("To", ""),
            "duration": int(payload.get("Duration", 0)),
            "recording_url": payload.get("RecordingUrl", ""),
        }

    async def close(self):
        await self.client.aclose()
