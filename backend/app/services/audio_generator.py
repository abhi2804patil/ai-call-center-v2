import asyncio
import io
import logging
import re
import uuid
from typing import Optional

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.script import Script
from app.models.script_audio import ScriptAudio
from app.services.sarvam_client import SarvamClient

logger = logging.getLogger(__name__)
settings = get_settings()


class AudioGenerator:
    def __init__(self, sarvam: SarvamClient | None = None, s3_client=None):
        self.sarvam = sarvam or SarvamClient()
        self.s3 = s3_client or boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.bucket = settings.AWS_S3_BUCKET

    async def generate_all_audio(self, db: AsyncSession, script_id: uuid.UUID) -> dict:
        result = await db.execute(select(Script).where(Script.id == script_id))
        script = result.scalar_one_or_none()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        script.audio_status = "generating"
        await db.flush()

        content = script.content
        voice_id = content.get("voice_id", "meera")
        languages = content.get("supported_languages", ["hi"])
        nodes = content.get("nodes", {})
        company_id = str(script.company_id)

        total = 0
        generated = 0
        failed = 0
        total_cost = 0.0
        files = []

        for node_key, node_config in nodes.items():
            text_map = node_config.get("text", {})
            for lang in languages:
                text = text_map.get(lang, "")
                if not text:
                    continue

                total += 1
                try:
                    audio_bytes, duration_ms = await self.sarvam.text_to_speech(
                        text=text,
                        language_code=lang,
                        voice=voice_id,
                    )

                    s3_key = f"audio/{company_id}/{script_id}/{node_key}_{lang}.wav"
                    await asyncio.to_thread(
                        self.s3.upload_fileobj,
                        io.BytesIO(audio_bytes),
                        self.bucket,
                        s3_key,
                        ExtraArgs={"ContentType": "audio/wav"},
                    )
                    audio_url = f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

                    existing = await db.execute(
                        select(ScriptAudio).where(
                            ScriptAudio.script_id == script_id,
                            ScriptAudio.node_key == node_key,
                            ScriptAudio.language_code == lang,
                        )
                    )
                    audio_record = existing.scalar_one_or_none()

                    if audio_record:
                        audio_record.voice_id = voice_id
                        audio_record.text_content = text
                        audio_record.audio_url = audio_url
                        audio_record.audio_duration_ms = duration_ms
                        audio_record.file_size_bytes = len(audio_bytes)
                        audio_record.generation_cost_credits = 1.0
                        audio_record.status = "ready"
                    else:
                        audio_record = ScriptAudio(
                            script_id=script_id,
                            node_key=node_key,
                            language_code=lang,
                            voice_id=voice_id,
                            text_content=text,
                            audio_url=audio_url,
                            audio_duration_ms=duration_ms,
                            file_size_bytes=len(audio_bytes),
                            generation_cost_credits=1.0,
                            status="ready",
                        )
                        db.add(audio_record)

                    await db.flush()
                    generated += 1
                    total_cost += 1.0
                    files.append({
                        "node_key": node_key,
                        "language_code": lang,
                        "audio_url": audio_url,
                        "duration_ms": duration_ms,
                        "status": "ready",
                    })
                    logger.info(f"Generated audio: {node_key}/{lang} for script {script_id}")

                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to generate audio for {node_key}/{lang}: {e}")
                    files.append({
                        "node_key": node_key,
                        "language_code": lang,
                        "status": "failed",
                        "error": str(e),
                    })

        script.audio_status = "ready" if failed == 0 else "failed"
        await db.flush()

        logger.info(
            f"Audio generation complete for script {script_id}: "
            f"total={total}, generated={generated}, failed={failed}"
        )

        return {
            "total_files": total,
            "generated": generated,
            "failed": failed,
            "total_cost_credits": total_cost,
            "files": files,
        }

    async def generate_single_audio(
        self,
        db: AsyncSession,
        script_id: uuid.UUID,
        node_key: str,
        language_code: str,
    ) -> ScriptAudio:
        result = await db.execute(select(Script).where(Script.id == script_id))
        script = result.scalar_one_or_none()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        content = script.content
        voice_id = content.get("voice_id", "meera")
        nodes = content.get("nodes", {})
        node_config = nodes.get(node_key)
        if not node_config:
            raise ValueError(f"Node '{node_key}' not found in script")

        text = node_config.get("text", {}).get(language_code, "")
        if not text:
            raise ValueError(f"No text for node '{node_key}' in language '{language_code}'")

        audio_bytes, duration_ms = await self.sarvam.text_to_speech(
            text=text,
            language_code=language_code,
            voice=voice_id,
        )

        company_id = str(script.company_id)
        s3_key = f"audio/{company_id}/{script_id}/{node_key}_{language_code}.wav"
        await asyncio.to_thread(
            self.s3.upload_fileobj,
            io.BytesIO(audio_bytes),
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": "audio/wav"},
        )
        audio_url = f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

        existing = await db.execute(
            select(ScriptAudio).where(
                ScriptAudio.script_id == script_id,
                ScriptAudio.node_key == node_key,
                ScriptAudio.language_code == language_code,
            )
        )
        audio_record = existing.scalar_one_or_none()

        if audio_record:
            audio_record.voice_id = voice_id
            audio_record.text_content = text
            audio_record.audio_url = audio_url
            audio_record.audio_duration_ms = duration_ms
            audio_record.file_size_bytes = len(audio_bytes)
            audio_record.generation_cost_credits = 1.0
            audio_record.status = "ready"
        else:
            audio_record = ScriptAudio(
                script_id=script_id,
                node_key=node_key,
                language_code=language_code,
                voice_id=voice_id,
                text_content=text,
                audio_url=audio_url,
                audio_duration_ms=duration_ms,
                file_size_bytes=len(audio_bytes),
                generation_cost_credits=1.0,
                status="ready",
            )
            db.add(audio_record)

        await db.flush()
        logger.info(f"Regenerated audio: {node_key}/{language_code} for script {script_id}")
        return audio_record

    async def preview_audio(self, text: str, language_code: str, voice_id: str) -> bytes:
        audio_bytes, _ = await self.sarvam.text_to_speech(
            text=text,
            language_code=language_code,
            voice=voice_id,
        )
        return audio_bytes

    async def generate_dynamic_audio(
        self,
        text: str,
        language_code: str,
        voice_id: str,
    ) -> bytes:
        sarvam = SarvamClient()
        try:
            sarvam.client = sarvam.client.__class__(
                timeout=3.0,
                headers={"api-subscription-key": sarvam.api_key},
            )
            audio_bytes, _ = await sarvam.text_to_speech(
                text=text,
                language_code=language_code,
                voice=voice_id,
            )
            return audio_bytes
        finally:
            await sarvam.close()

    async def get_audio_for_node(
        self,
        db: AsyncSession,
        script_id: uuid.UUID,
        node_key: str,
        language_code: str,
    ) -> tuple[str, int]:
        result = await db.execute(
            select(ScriptAudio).where(
                ScriptAudio.script_id == script_id,
                ScriptAudio.node_key == node_key,
                ScriptAudio.language_code == language_code,
                ScriptAudio.status == "ready",
            )
        )
        audio = result.scalar_one_or_none()
        if not audio:
            raise ValueError(
                f"Audio not found for script={script_id}, node={node_key}, lang={language_code}"
            )
        return audio.audio_url, audio.audio_duration_ms

    def fill_dynamic_slots(self, text: str, customer_data: dict, language_code: str) -> tuple[str, str]:
        slot_pattern = re.compile(r"\{(\w+)\}")
        slots_found = slot_pattern.findall(text)

        if not slots_found:
            return text, text

        filled_text = text
        for slot in slots_found:
            value = customer_data.get(slot, slot)
            if isinstance(value, (int, float)):
                if language_code == "hi":
                    value_str = self._number_to_hindi_words(int(value))
                elif language_code == "en":
                    value_str = self._number_to_english_words(int(value))
                else:
                    value_str = str(value)
            else:
                value_str = str(value)
            filled_text = filled_text.replace(f"{{{slot}}}", value_str)

        static_text = slot_pattern.sub("", text).replace("  ", " ").strip()
        return static_text, filled_text

    @staticmethod
    def _number_to_hindi_words(number: int) -> str:
        if number == 0:
            return "shunya"

        ones = ["", "ek", "do", "teen", "chaar", "paanch", "chhah", "saat", "aath", "nau"]
        tens_special = [
            "", "", "bees", "tees", "chaalees", "pachaas",
            "saath", "sattar", "assi", "nabbe",
        ]
        teens = [
            "das", "gyaarah", "baarah", "terah", "chaudah", "pandrah",
            "solah", "satrah", "aathaarah", "unees",
        ]

        parts = []
        if number >= 10000000:
            crore = number // 10000000
            parts.append(f"{ones[crore] if crore < 10 else str(crore)} crore")
            number %= 10000000

        if number >= 100000:
            lakh = number // 100000
            parts.append(f"{ones[lakh] if lakh < 10 else str(lakh)} lakh")
            number %= 100000

        if number >= 1000:
            hazaar = number // 1000
            if hazaar < 10:
                parts.append(f"{ones[hazaar]} hazaar")
            else:
                parts.append(f"{str(hazaar)} hazaar")
            number %= 1000

        if number >= 100:
            sau = number // 100
            parts.append(f"{ones[sau]} sau")
            number %= 100

        if number >= 20:
            decade = number // 10
            remainder = number % 10
            parts.append(tens_special[decade])
            if remainder:
                parts.append(ones[remainder])
        elif number >= 10:
            parts.append(teens[number - 10])
        elif number > 0:
            parts.append(ones[number])

        return " ".join(p for p in parts if p)

    @staticmethod
    def _number_to_english_words(number: int) -> str:
        if number == 0:
            return "zero"

        ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
        teens = [
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
            "sixteen", "seventeen", "eighteen", "nineteen",
        ]
        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

        parts = []
        if number >= 10000000:
            crore = number // 10000000
            parts.append(f"{ones[crore] if crore < 10 else str(crore)} crore")
            number %= 10000000

        if number >= 100000:
            lakh = number // 100000
            parts.append(f"{ones[lakh] if lakh < 10 else str(lakh)} lakh")
            number %= 100000

        if number >= 1000:
            thousands = number // 1000
            if thousands < 10:
                parts.append(f"{ones[thousands]} thousand")
            else:
                parts.append(f"{str(thousands)} thousand")
            number %= 1000

        if number >= 100:
            hundreds = number // 100
            parts.append(f"{ones[hundreds]} hundred")
            number %= 100

        if number >= 20:
            decade = number // 10
            remainder = number % 10
            if remainder:
                parts.append(f"{tens[decade]} {ones[remainder]}")
            else:
                parts.append(tens[decade])
        elif number >= 10:
            parts.append(teens[number - 10])
        elif number > 0:
            parts.append(ones[number])

        return " ".join(p for p in parts if p)
