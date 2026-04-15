import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.call_log import CallLog
from app.models.script_audio import ScriptAudio
from app.services.audio_generator import AudioGenerator
from app.services.gemini_client import GeminiIntentClassifier
from app.services.sarvam_client import SarvamClient
from app.services.script_engine import ScriptEngine

logger = logging.getLogger(__name__)
settings = get_settings()


class CallState(str, Enum):
    CONNECTED = "connected"
    PLAYING_AUDIO = "playing_audio"
    LISTENING = "listening"
    PROCESSING = "processing"
    ENDING = "ending"
    COMPLETED = "completed"
    FAILED = "failed"


class CallOrchestrator:
    MAX_FALLBACK_RETRIES = 3

    def __init__(
        self,
        call_id: str,
        campaign_id: str | None,
        company_id: str,
        phone_number: str,
        script_content: dict,
        customer_data: dict,
        db: AsyncSession,
        script_id: str | uuid.UUID | None = None,
        sarvam: SarvamClient | None = None,
        gemini: GeminiIntentClassifier | None = None,
        audio_generator: AudioGenerator | None = None,
    ):
        self.call_id = call_id
        self.campaign_id = campaign_id
        self.company_id = company_id
        self.phone_number = phone_number
        self.script_content = script_content
        self.customer_data = customer_data
        self.db = db
        self.script_id: uuid.UUID | None = uuid.UUID(str(script_id)) if script_id else None

        self.detected_language = script_content.get("default_language", "hi")
        self.current_node = "greeting"
        self.transcript: list[dict] = []
        self.state = CallState.CONNECTED
        self.call_sid: str | None = None
        self.fallback_count = 0

        self.sarvam = sarvam or SarvamClient()
        self.gemini = gemini or GeminiIntentClassifier()
        self.audio_generator = audio_generator or AudioGenerator(sarvam=self.sarvam)
        self.script_engine = ScriptEngine()

        self.redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if not self.redis:
            self.redis = aioredis.from_url(settings.REDIS_URL)
        return self.redis

    async def _publish_event(self, event_type: str, data: dict | None = None):
        try:
            redis_client = await self._get_redis()
            event = {
                "type": event_type,
                "call_id": self.call_id,
                "state": self.state.value,
                "current_node": self.current_node,
                "phone_number": self.phone_number,
                "language": self.detected_language,
                "transcript": self.transcript[-5:],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if data:
                event.update(data)
            await redis_client.publish(f"calls:{self.company_id}", json.dumps(event))
        except Exception as e:
            logger.error(f"Failed to publish Redis event: {e}")

    async def start_call(self, call_sid: str):
        self.call_sid = call_sid
        self.state = CallState.CONNECTED
        logger.info(f"Call started: {self.call_id}, phone={self.phone_number}")

        self.detected_language = self.script_content.get("default_language", "hi")
        self.current_node = "greeting"

        await self._publish_event("call_started")
        await self.play_node("greeting")
        self.state = CallState.LISTENING
        await self._publish_event("listening")

    async def play_node(self, node_key: str):
        self.state = CallState.PLAYING_AUDIO
        self.current_node = node_key
        logger.info(f"Playing node '{node_key}' for call {self.call_id}")

        node_config = self.script_engine.get_node(self.script_content, node_key)
        if not node_config:
            logger.error(f"Node '{node_key}' not found in script")
            await self.handle_error(ValueError(f"Node '{node_key}' not found"))
            return

        dynamic_slots = node_config.get("dynamic_slots", [])
        text_template = node_config.get("text", {}).get(self.detected_language, "")

        if not text_template:
            fallback_lang = self.script_content.get("default_language", "hi")
            text_template = node_config.get("text", {}).get(fallback_lang, "")

        if not text_template:
            logger.error(f"No text for node '{node_key}' in any language")
            await self.handle_error(ValueError(f"No text for node '{node_key}'"))
            return

        has_dynamic_data = dynamic_slots and any(
            slot in self.customer_data for slot in dynamic_slots
        )

        if has_dynamic_data:
            _, full_text = self.audio_generator.fill_dynamic_slots(
                text_template, self.customer_data, self.detected_language
            )
            voice_id = self.script_content.get("voice_id", "meera")

            try:
                audio_bytes = await self.audio_generator.generate_dynamic_audio(
                    full_text, self.detected_language, voice_id
                )
                from app.services.telephony_client import TelephonyClient
                telephony = TelephonyClient()
                await telephony.play_audio_bytes(self.call_sid, audio_bytes)
                logger.info(f"Dynamic audio played for node '{node_key}': {full_text[:50]}")
            except Exception as e:
                logger.error(f"Dynamic TTS failed for node '{node_key}': {e}")
                try:
                    audio_url, _ = await self.audio_generator.get_audio_for_node(
                        self.db, uuid.UUID(self.call_id) if self._is_valid_uuid(self.call_id) else uuid.uuid4(),
                        node_key, self.detected_language
                    )
                    telephony = TelephonyClient()
                    await telephony.play_audio(self.call_sid, audio_url)
                except Exception:
                    pass
                full_text = text_template
        else:
            full_text = text_template
            try:
                script_id = self._get_script_id()
                audio_url, duration_ms = await self.audio_generator.get_audio_for_node(
                    self.db, script_id, node_key, self.detected_language
                )
                from app.services.telephony_client import TelephonyClient
                telephony = TelephonyClient()
                await telephony.play_audio(self.call_sid, audio_url)
                logger.info(f"Pre-generated audio played for node '{node_key}', duration={duration_ms}ms")
            except Exception as e:
                logger.error(f"Failed to play pre-generated audio for '{node_key}': {e}")

        self.transcript.append({
            "role": "ai",
            "text": full_text,
            "node_key": node_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        next_action = node_config.get("next_action", "listen")
        if next_action == "end":
            await self.end_call()
        elif next_action == "transfer":
            await self.handle_transfer()
        else:
            self.state = CallState.LISTENING
            await self._publish_event("node_played", {"node_key": node_key})

    async def process_customer_audio(self, audio_bytes: bytes):
        if self.state != CallState.LISTENING:
            logger.warning(f"Received audio while in state {self.state}, buffering")
            return

        self.state = CallState.PROCESSING
        logger.info(f"Processing customer audio for call {self.call_id}")

        try:
            stt_result = await self.sarvam.speech_to_text(audio_bytes, self.detected_language)
            transcribed_text = stt_result.get("text", "")
            detected_lang = stt_result.get("language_code", self.detected_language)

            if self.detected_language == "auto" and detected_lang != "auto":
                self.detected_language = detected_lang
                logger.info(f"Language detected: {self.detected_language}")

            if not transcribed_text.strip():
                logger.info("Empty transcription, playing fallback")
                self.fallback_count += 1
                if self.fallback_count >= self.MAX_FALLBACK_RETRIES:
                    await self._end_due_to_max_fallback()
                    return
                await self.play_node("fallback")
                return

            intent_map = self.script_content.get("intent_map", {})
            intent_result = await self.gemini.classify_intent(
                transcribed_text, intent_map, self.detected_language
            )

            intent = intent_result.get("intent", "fallback")
            confidence = intent_result.get("confidence", 0.0)

            if confidence < 0.4:
                intent = "fallback"

            self.transcript.append({
                "role": "customer",
                "text": transcribed_text,
                "intent": intent,
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            next_node = self.script_engine.get_next_node_for_intent(
                self.script_content, self.current_node, intent
            )

            if intent == "fallback":
                self.fallback_count += 1
                if self.fallback_count >= self.MAX_FALLBACK_RETRIES:
                    await self._end_due_to_max_fallback()
                    return
            else:
                self.fallback_count = 0

            logger.info(
                f"Call {self.call_id}: customer said '{transcribed_text[:50]}', "
                f"intent={intent} (conf={confidence:.2f}), next_node={next_node}"
            )

            self.current_node = next_node
            await self.play_node(next_node)

        except Exception as e:
            logger.error(f"Error processing customer audio: {e}")
            await self.handle_error(e)

    async def handle_transfer(self):
        self.state = CallState.ENDING
        logger.info(f"Transferring call {self.call_id}")

        escalation = self.script_content.get("escalation", {})
        fallback_number = escalation.get("fallback_number", "")

        transfer_node = self.script_engine.get_node(self.script_content, "transfer")
        if transfer_node:
            text = transfer_node.get("text", {}).get(self.detected_language, "")
            if text:
                self.transcript.append({
                    "role": "ai",
                    "text": text,
                    "node_key": "transfer",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        if fallback_number:
            try:
                from app.services.telephony_client import TelephonyClient
                telephony = TelephonyClient()
                await telephony.transfer_call(self.call_sid, fallback_number)
                logger.info(f"Call {self.call_id} transferred to {fallback_number}")
            except Exception as e:
                logger.error(f"Transfer failed: {e}")

        self.transcript.append({
            "role": "system",
            "text": f"Call transferred to {fallback_number}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        await self._publish_event("call_transferred", {"transfer_to": fallback_number})
        await self._save_call_log("transferred")

    async def end_call(self):
        if self.state == CallState.COMPLETED:
            return

        self.state = CallState.ENDING
        logger.info(f"Ending call {self.call_id}")

        closing_node = self.script_engine.get_node(self.script_content, "closing")
        if closing_node and self.current_node != "closing":
            text = closing_node.get("text", {}).get(self.detected_language, "")
            if text:
                self.transcript.append({
                    "role": "ai",
                    "text": text,
                    "node_key": "closing",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        await self._save_call_log("completed")
        self.state = CallState.COMPLETED
        await self._publish_event("call_completed")

        try:
            from app.workers.summary_worker import generate_call_summary
            generate_call_summary.delay(self.call_id)
        except Exception as e:
            logger.error(f"Failed to trigger summary generation: {e}")

    async def handle_error(self, error: Exception):
        logger.error(f"Call {self.call_id} error: {error}")

        if self.state not in (CallState.ENDING, CallState.COMPLETED, CallState.FAILED):
            self.fallback_count += 1
            if self.fallback_count < self.MAX_FALLBACK_RETRIES:
                try:
                    await self.play_node("fallback")
                    self.state = CallState.LISTENING
                    return
                except Exception:
                    pass

            self.state = CallState.FAILED
            await self._save_call_log("failed")
            await self._publish_event("call_failed", {"error": str(error)})

    async def _end_due_to_max_fallback(self):
        logger.info(f"Call {self.call_id}: max fallback retries reached, ending call")
        self.transcript.append({
            "role": "system",
            "text": "Call ended: maximum fallback retries reached",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await self.end_call()

    async def _save_call_log(self, final_status: str):
        try:
            started_at = None
            if self.transcript:
                first_ts = self.transcript[0].get("timestamp")
                if first_ts:
                    started_at = datetime.fromisoformat(first_ts)

            ended_at = datetime.now(timezone.utc)
            duration = int((ended_at - started_at).total_seconds()) if started_at else 0

            result = await self.db.execute(
                select(CallLog).where(CallLog.id == self.call_id)
            )
            call_log = result.scalar_one_or_none()

            if call_log:
                call_log.status = final_status
                call_log.ended_at = ended_at
                call_log.duration_seconds = duration
                call_log.transcript = self.transcript
                call_log.language_detected = self.detected_language
            else:
                call_log = CallLog(
                    id=uuid.UUID(self.call_id) if self._is_valid_uuid(self.call_id) else uuid.uuid4(),
                    campaign_id=uuid.UUID(self.campaign_id) if self.campaign_id and self._is_valid_uuid(self.campaign_id) else None,
                    company_id=uuid.UUID(self.company_id),
                    phone_number=self.phone_number,
                    direction="outbound",
                    status=final_status,
                    language_detected=self.detected_language,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_seconds=duration,
                    transcript=self.transcript,
                    metadata_=self.customer_data,
                )
                self.db.add(call_log)

            await self.db.flush()
            logger.info(f"Call log saved: {self.call_id}, status={final_status}")
        except Exception as e:
            logger.error(f"Failed to save call log: {e}")

    def _get_script_id(self) -> uuid.UUID:
        if self.script_id is None:
            raise ValueError("script_id was not provided to CallOrchestrator")
        return self.script_id

    @staticmethod
    def _is_valid_uuid(val: str) -> bool:
        try:
            uuid.UUID(val)
            return True
        except (ValueError, AttributeError):
            return False

    async def cleanup(self):
        if self.redis:
            await self.redis.close()
        await self.sarvam.close()
