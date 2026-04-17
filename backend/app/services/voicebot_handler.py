"""
Real-time voicebot handler for Twilio Media Streams WebSocket audio streaming.

Flow:
  Twilio connects call → streams customer audio via WebSocket (mulaw 8kHz)
  → Convert mulaw→PCM → Buffer audio chunks → Sarvam STT
  → Gemini intent classification → Script engine next node
  → Sarvam TTS → convert PCM→mulaw → stream audio back via WebSocket
"""

import asyncio
import audioop
import base64
import io
import json
import logging
import struct
import time
import uuid
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.call_log import CallLog
from app.models.campaign import Campaign
from app.models.script import Script
from app.services.audio_generator import AudioGenerator
from app.services.gemini_client import GeminiIntentClassifier
from app.services.sarvam_client import SarvamClient
from app.services.script_engine import ScriptEngine

logger = logging.getLogger(__name__)
settings = get_settings()

# Audio config: Twilio Media Streams use mulaw 8kHz mono
# We convert to/from 16-bit linear PCM for processing
SAMPLE_RATE = 8000
BYTES_PER_SAMPLE = 2  # 16-bit PCM (after mulaw decode)
CHANNELS = 1
# Silence detection
SILENCE_THRESHOLD = 500  # amplitude threshold for silence detection
SILENCE_DURATION_MS = 800  # ms of silence before processing (short utterances)
SILENCE_DURATION_LONG_MS = 1200  # ms for longer utterances (>2s of speech)
# Minimum audio to process (avoid processing noise/clicks)
MIN_AUDIO_DURATION_MS = 500
MAX_AUDIO_DURATION_MS = 30000


def _create_wav_header(data_size: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Create a WAV file header for raw PCM data."""
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,  # chunk size
        1,  # PCM format
        CHANNELS,
        sample_rate,
        sample_rate * CHANNELS * BYTES_PER_SAMPLE,  # byte rate
        CHANNELS * BYTES_PER_SAMPLE,  # block align
        BYTES_PER_SAMPLE * 8,  # bits per sample
        b"data",
        data_size,
    )
    return header


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Wrap raw PCM bytes in a WAV container."""
    header = _create_wav_header(len(pcm_data), sample_rate)
    return header + pcm_data


def _is_silence(pcm_chunk: bytes, threshold: int = SILENCE_THRESHOLD) -> bool:
    """Check if a PCM audio chunk is silence."""
    if len(pcm_chunk) < 2:
        return True
    samples = struct.unpack(f"<{len(pcm_chunk) // 2}h", pcm_chunk)
    rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
    return rms < threshold


def _mulaw_to_pcm(mulaw_data: bytes) -> bytes:
    """Convert mulaw audio to 16-bit linear PCM."""
    return audioop.ulaw2lin(mulaw_data, 2)


def _pcm_to_mulaw(pcm_data: bytes) -> bytes:
    """Convert 16-bit linear PCM to mulaw."""
    return audioop.lin2ulaw(pcm_data, 2)


class VoicebotSession:
    """Manages a single voicebot call session over WebSocket."""

    def __init__(
        self,
        websocket: WebSocket,
        call_sid: str,
        script_content: dict,
        db: AsyncSession,
        call_log: CallLog | None = None,
        customer_data: dict | None = None,
        script_id: uuid.UUID | None = None,
        company_id: str = "",
        campaign_id: str | None = None,
    ):
        self.ws = websocket
        self.call_sid = call_sid
        self.script_content = script_content
        self.db = db
        self.call_log = call_log
        self.customer_data = customer_data or {}
        self.script_id = script_id
        self.company_id = company_id
        self.campaign_id = campaign_id

        # AI services
        self.sarvam = SarvamClient()
        self.gemini = GeminiIntentClassifier()
        self.audio_gen = AudioGenerator(sarvam=self.sarvam)
        self.script_engine = ScriptEngine()

        # Twilio stream state
        self.stream_sid = ""
        self._send_seq = 0

        # Pre-loaded audio cache: {node_key: audio_bytes}
        self._audio_cache: dict[str, bytes] = {}

        # Conversation state
        self.detected_language = script_content.get("default_language", "hi")
        self.current_node = "greeting"
        self.transcript: list[dict] = []
        self.fallback_count = 0
        self.max_fallbacks = 3
        self.is_playing = False
        self.is_active = True

        # Audio buffer for customer speech (stores linear PCM)
        self._audio_buffer = bytearray()
        self._silence_start: float | None = None
        self._speech_started = False

    async def _preload_audio(self):
        """Load all pre-generated audio into memory for instant playback."""
        if not self.script_id:
            return
        try:
            from app.models.script_audio import ScriptAudio
            lang_short = self.detected_language.split("-")[0] if "-" in self.detected_language else self.detected_language
            result = await self.db.execute(
                select(ScriptAudio).where(
                    ScriptAudio.script_id == self.script_id,
                    ScriptAudio.language_code == lang_short,
                    ScriptAudio.status == "ready",
                )
            )
            for record in result.scalars().all():
                if record.audio_url and record.audio_url.startswith("data:"):
                    b64_data = record.audio_url.split(",", 1)[1]
                    self._audio_cache[record.node_key] = base64.b64decode(b64_data)
            logger.info(f"Preloaded {len(self._audio_cache)} audio files into memory")
        except Exception as e:
            logger.warning(f"Failed to preload audio: {e}")

    async def run(self):
        """Main loop: read WebSocket concurrently while playing audio."""
        try:
            logger.info(f"Voicebot session started: call_sid={self.call_sid}")

            # Start reading from WebSocket in background
            self._reader_task = asyncio.create_task(self._read_loop())

            # Play greeting immediately from cache
            await self._play_node("greeting")

            # Wait for reader to finish (runs until call ends or disconnect)
            await self._reader_task

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: call_sid={self.call_sid}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Voicebot session error: {e}", exc_info=True)
        finally:
            await self._end_session()

    async def _read_loop(self):
        """Continuously read from WebSocket and handle messages."""
        msg_count = 0
        while self.is_active:
            try:
                message = await asyncio.wait_for(self.ws.receive(), timeout=60.0)
            except asyncio.TimeoutError:
                logger.info(f"WebSocket timeout, ending call {self.call_sid}")
                break
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnect in read loop after {msg_count} messages")
                break

            msg_count += 1
            msg_type = message.get("type", "unknown")

            if msg_type == "websocket.disconnect":
                logger.info(f"WebSocket disconnect event after {msg_count} messages")
                break

            if "text" in message:
                if msg_count <= 5:
                    logger.info(f"Read loop msg #{msg_count}: {message['text'][:150]}")
                await self._handle_control_message(message["text"])
            elif "bytes" in message:
                if msg_count <= 5:
                    logger.info(f"Read loop msg #{msg_count}: binary {len(message['bytes'])}b")

    async def _handle_control_message(self, text: str):
        """Handle JSON control messages from Twilio Media Streams.

        Twilio sends events: connected, start, media, stop, mark.
        Audio payload is base64-encoded mulaw at 8kHz.
        """
        try:
            data = json.loads(text)
            event = data.get("event", "")

            if event == "connected":
                logger.info(f"Twilio stream connected: protocol={data.get('protocol')}")
            elif event == "start":
                start_data = data.get("start", {})
                self.stream_sid = data.get("streamSid", "")
                self.call_sid = start_data.get("callSid", self.call_sid)
                logger.info(
                    f"Twilio stream started: call_sid={self.call_sid}, "
                    f"stream_sid={self.stream_sid}"
                )
            elif event == "media":
                payload = data.get("media", {}).get("payload", "")
                if payload:
                    mulaw_bytes = base64.b64decode(payload)
                    # Convert mulaw to linear PCM for processing
                    pcm_bytes = _mulaw_to_pcm(mulaw_bytes)
                    await self._handle_audio_chunk(pcm_bytes)
            elif event == "stop":
                logger.info(f"Twilio stream stopped: call_sid={self.call_sid}")
                self.is_active = False
            elif event == "mark":
                logger.debug(f"Twilio mark event: {data.get('mark', {}).get('name')}")
            else:
                logger.debug(f"Unknown Twilio event: {event}")
        except json.JSONDecodeError:
            logger.warning(f"Non-JSON text message received: {text[:100]}")

    async def _handle_audio_chunk(self, chunk: bytes):
        """Buffer incoming PCM audio and detect end-of-speech."""
        if self.is_playing or not self.is_active:
            return

        is_silent = _is_silence(chunk)
        now = time.time()

        if not is_silent:
            # Customer is speaking
            self._speech_started = True
            self._silence_start = None
            self._audio_buffer.extend(chunk)
        else:
            if self._speech_started:
                # Customer was speaking, now silent
                self._audio_buffer.extend(chunk)

                if self._silence_start is None:
                    self._silence_start = now
                else:
                    # Adaptive silence: short speech (< 2s) → 800ms, longer → 1200ms
                    speech_ms = len(self._audio_buffer) / (SAMPLE_RATE * BYTES_PER_SAMPLE) * 1000
                    threshold = SILENCE_DURATION_MS if speech_ms < 2000 else SILENCE_DURATION_LONG_MS
                    if (now - self._silence_start) * 1000 < threshold:
                        return
                    # End of utterance detected
                    await self._process_buffered_audio()

        # Safety: don't buffer more than max duration
        buffer_duration_ms = len(self._audio_buffer) / (SAMPLE_RATE * BYTES_PER_SAMPLE) * 1000
        if buffer_duration_ms >= MAX_AUDIO_DURATION_MS:
            await self._process_buffered_audio()

    async def _process_buffered_audio(self):
        """Process the buffered customer audio through STT → Intent → Response."""
        if not self._audio_buffer:
            self._reset_buffer()
            return

        audio_pcm = bytes(self._audio_buffer)
        self._reset_buffer()

        # Check minimum duration
        duration_ms = len(audio_pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE) * 1000
        if duration_ms < MIN_AUDIO_DURATION_MS:
            logger.debug(f"Audio too short ({duration_ms:.0f}ms), ignoring")
            return

        logger.info(f"Processing customer audio: {duration_ms:.0f}ms")

        try:
            # 1. Speech-to-Text
            wav_data = _pcm_to_wav(audio_pcm)
            stt_result = await self.sarvam.speech_to_text(wav_data, self.detected_language)
            text = stt_result.get("text", "").strip()
            detected_lang = stt_result.get("language_code", self.detected_language)

            if detected_lang and detected_lang != "auto":
                self.detected_language = detected_lang

            if not text:
                logger.info("Empty transcription, playing fallback")
                self.fallback_count += 1
                if self.fallback_count >= self.max_fallbacks:
                    await self._play_node("closing")
                    self.is_active = False
                    return
                await self._play_node("fallback")
                return

            logger.info(f"Customer said: '{text}' (lang={self.detected_language})")

            # 2. Intent Classification — fast keyword match first, Gemini fallback
            intent_map = self.script_content.get("intent_map", {})
            intent, confidence = self._fast_keyword_match(text, intent_map)

            if not intent:
                # No fast match — use Gemini
                intent_result = await self.gemini.classify_intent(
                    text, intent_map, self.detected_language
                )
                intent = intent_result.get("intent", "fallback")
                confidence = intent_result.get("confidence", 0.0)

            if confidence < 0.2:
                intent = "fallback"

            # Record in transcript
            self.transcript.append({
                "role": "customer",
                "text": text,
                "intent": intent,
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            logger.info(f"Intent: {intent} (confidence={confidence:.2f})")

            # 3. Navigate to next node
            next_node = self.script_engine.get_next_node_for_intent(
                self.script_content, self.current_node, intent
            )

            if intent == "fallback":
                self.fallback_count += 1
                if self.fallback_count >= self.max_fallbacks:
                    await self._play_node("closing")
                    self.is_active = False
                    return
            else:
                self.fallback_count = 0

            # 4. Play response
            self.current_node = next_node
            await self._play_node(next_node)

            # Check if this node ends the call
            node_config = self.script_engine.get_node(self.script_content, next_node)
            if node_config and node_config.get("next_action") == "end":
                self.is_active = False
            elif node_config and node_config.get("next_action") == "transfer":
                self.transcript.append({
                    "role": "system",
                    "text": "Call transferred to human agent",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                self.is_active = False

        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)
            self.fallback_count += 1
            if self.fallback_count >= self.max_fallbacks:
                self.is_active = False
            else:
                await self._play_node("fallback")

    async def _play_node(self, node_key: str):
        """Generate TTS for a node and stream audio to Twilio."""
        self.is_playing = True
        self.current_node = node_key

        try:
            node_config = self.script_engine.get_node(self.script_content, node_key)
            if not node_config:
                logger.error(f"Node '{node_key}' not found")
                self.is_playing = False
                return

            # Get text for current language
            text = node_config.get("text", {}).get(self.detected_language, "")
            if not text:
                fallback_lang = self.script_content.get("default_language", "hi")
                text = node_config.get("text", {}).get(fallback_lang, "")

            if not text:
                logger.error(f"No text for node '{node_key}'")
                self.is_playing = False
                return

            # Fill dynamic slots
            dynamic_slots = node_config.get("dynamic_slots", [])
            if dynamic_slots and self.customer_data:
                _, text = self.audio_gen.fill_dynamic_slots(
                    text, self.customer_data, self.detected_language
                )

            # Try cached audio first, then live TTS
            audio_bytes = self._audio_cache.get(node_key)
            if audio_bytes:
                logger.info(f"Using cached audio for '{node_key}'")

            if not audio_bytes:
                # Live TTS generation
                voice_id = self.script_content.get("voice_id", "priya")
                audio_bytes, duration_ms = await self.sarvam.text_to_speech(
                    text, self.detected_language, voice=voice_id, sample_rate=SAMPLE_RATE
                )
                logger.info(f"Live TTS for '{node_key}': {duration_ms}ms")

            # Record in transcript
            self.transcript.append({
                "role": "ai",
                "text": text,
                "node_key": node_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Stream audio to Twilio via WebSocket
            await self._send_audio(audio_bytes)

        except Exception as e:
            logger.error(f"Error playing node '{node_key}': {e}", exc_info=True)
        finally:
            self.is_playing = False

    async def _send_audio(self, audio_bytes: bytes):
        """Send audio to Twilio over WebSocket.

        Strips WAV header if present, converts linear PCM to mulaw,
        and sends as base64-encoded media events matching Twilio's format.
        """
        try:
            # Strip WAV header if present
            pcm_data = audio_bytes
            if audio_bytes[:4] == b"RIFF" and len(audio_bytes) > 44:
                pcm_data = audio_bytes[44:]

            # Convert linear PCM to mulaw for Twilio
            mulaw_data = _pcm_to_mulaw(pcm_data)

            # Send in 20ms chunks (160 bytes mulaw = 20ms at 8kHz)
            CHUNK_SIZE = 160
            chunk_num = 0
            for i in range(0, len(mulaw_data), CHUNK_SIZE):
                chunk = mulaw_data[i : i + CHUNK_SIZE]
                self._send_seq += 1
                chunk_num += 1
                chunk_b64 = base64.b64encode(chunk).decode()
                message = json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": chunk_b64,
                    },
                })
                await self.ws.send_text(message)

                # Pace at ~real-time: yield every 10 chunks (200ms)
                if chunk_num % 10 == 0:
                    await asyncio.sleep(0.02)

            # Send a mark event to know when audio finishes playing
            mark_name = f"audio_{self._send_seq}"
            await self.ws.send_text(json.dumps({
                "event": "mark",
                "streamSid": self.stream_sid,
                "mark": {"name": mark_name},
            }))

            # Wait for audio to finish playing on customer's end
            duration_s = len(pcm_data) / (SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS)
            await asyncio.sleep(duration_s + 0.2)

        except Exception as e:
            logger.error(f"Failed to send audio: {e}")

    @staticmethod
    def _fast_keyword_match(text: str, intent_map: dict) -> tuple[str | None, float]:
        """Fast keyword matching for obvious intents — skips Gemini."""
        text_lower = text.lower().strip()
        AFFIRMATIVE = {"haan", "ha", "haa", "ji", "ji haan", "haan ji", "yes", "ok",
                       "okay", "theek hai", "bilkul", "zaroor", "sure", "han",
                       "हाँ", "हां", "जी", "जी हाँ", "हाँ जी", "ठीक है", "बिल्कुल"}
        NEGATIVE = {"nahi", "nhi", "no", "nope", "mat", "naa", "na",
                    "नहीं", "नही", "ना", "मत"}

        if text_lower in AFFIRMATIVE:
            return "interested", 0.95
        if text_lower in NEGATIVE:
            return "not_interested", 0.95

        for intent_name, keywords in intent_map.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    return intent_name, 0.85

        return None, 0.0

    def _reset_buffer(self):
        """Reset the audio buffer and speech detection state."""
        self._audio_buffer = bytearray()
        self._silence_start = None
        self._speech_started = False

    async def _end_session(self):
        """Save call log and clean up resources."""
        logger.info(f"Ending voicebot session: call_sid={self.call_sid}")

        try:
            if self.call_log:
                self.call_log.status = "completed"
                self.call_log.ended_at = datetime.now(timezone.utc)
                self.call_log.transcript = self.transcript
                self.call_log.language_detected = self.detected_language

                if self.call_log.started_at:
                    delta = datetime.now(timezone.utc) - self.call_log.started_at
                    self.call_log.duration_seconds = int(delta.total_seconds())

                await self.db.commit()
                logger.info(f"Call log updated: {self.call_log.id}")

                try:
                    from app.workers.summary_worker import generate_call_summary
                    generate_call_summary.delay(str(self.call_log.id))
                except Exception as e:
                    logger.error(f"Failed to trigger summary: {e}")

        except Exception as e:
            logger.error(f"Failed to save call log: {e}")

        try:
            await self.sarvam.close()
        except Exception:
            pass


async def handle_voicebot_websocket(
    websocket: WebSocket,
    db: AsyncSession,
):
    """Entry point for Twilio Media Streams WebSocket connections.

    Twilio's <Connect><Stream> connects directly to this WebSocket.
    We accept first, wait for the Start event to get call metadata,
    then look up the script and begin the AI conversation.
    """
    await websocket.accept()
    logger.info("Voicebot WebSocket connected, waiting for Start event...")

    call_sid = ""
    stream_sid = ""

    # Wait for Connected and Start events from Twilio
    try:
        for i in range(20):
            message = await asyncio.wait_for(websocket.receive(), timeout=15.0)

            msg_type = message.get("type", "unknown")
            if "text" in message:
                logger.info(f"WS handshake msg #{i}: type={msg_type}, text={message['text'][:200]}")
                data = json.loads(message["text"])
            elif "bytes" in message:
                logger.info(f"WS handshake msg #{i}: type={msg_type}, bytes={len(message['bytes'])}b")
                continue
            else:
                logger.info(f"WS handshake msg #{i}: type={msg_type}, keys={list(message.keys())}")
                if msg_type == "websocket.disconnect":
                    logger.error("WebSocket disconnected during handshake")
                    return
                continue

            event = data.get("event", "")

            if event == "connected":
                logger.info(f"Twilio stream connected: {data}")
            elif event == "start":
                start_data = data.get("start", {})
                call_sid = start_data.get("callSid", "")
                stream_sid = data.get("streamSid", "")
                logger.info(f"Twilio stream started: call_sid={call_sid}, stream_sid={stream_sid}")
                break
            elif event == "stop":
                logger.info("Call ended before starting")
                return
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for Start event")
        await websocket.close(code=4000, reason="Timeout waiting for Start")
        return
    except Exception as e:
        logger.error(f"Error during WebSocket handshake: {e}", exc_info=True)
        return

    # Look up call log and script
    call_log = None
    script_content = None
    script_id = None
    company_id = ""
    campaign_id = None
    customer_data = {}

    if call_sid:
        result = await db.execute(
            select(CallLog).where(CallLog.exotel_call_sid == call_sid)
        )
        call_log = result.scalar_one_or_none()

        if call_log:
            call_log.status = "in-progress"
            call_log.started_at = datetime.now(timezone.utc)
            company_id = str(call_log.company_id)
            campaign_id = str(call_log.campaign_id) if call_log.campaign_id else None
            customer_data = call_log.metadata_ or {}

            if call_log.campaign_id:
                camp_result = await db.execute(
                    select(Campaign).where(Campaign.id == call_log.campaign_id)
                )
                campaign = camp_result.scalar_one_or_none()
                if campaign:
                    script_result = await db.execute(
                        select(Script).where(Script.id == campaign.script_id)
                    )
                    script = script_result.scalar_one_or_none()
                    if script:
                        script_content = script.content
                        script_id = script.id

            await db.flush()

    if not script_content:
        # Fall back to any active script (for testing or direct calls)
        result = await db.execute(
            select(Script).where(Script.is_active == True).limit(1)
        )
        script = result.scalar_one_or_none()
        if script:
            script_content = script.content
            script_id = script.id
            if not company_id:
                company_id = str(script.company_id)

    if not script_content:
        logger.error(f"No script found for call_sid={call_sid}")
        await websocket.close(code=4004, reason="No script configured")
        return

    session = VoicebotSession(
        websocket=websocket,
        call_sid=call_sid,
        script_content=script_content,
        db=db,
        call_log=call_log,
        customer_data=customer_data,
        script_id=script_id,
        company_id=company_id,
        campaign_id=campaign_id,
    )
    session.stream_sid = stream_sid

    # Preload all audio into memory for instant playback
    await session._preload_audio()

    await session.run()
